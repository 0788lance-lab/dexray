"""Core swap parser: detect BUY/SELL from pre/postTokenBalances diff."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from dexray.core import Swap
from dexray.solana.rpc import MultiRPC
from dexray.solana.metadata import TokenResolver

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
LAMPORTS_PER_SOL = 1_000_000_000
STABLECOINS = {USDC, USDT}
QUOTE_PRIORITY = (USDC, USDT, WSOL)
QUOTE_MINTS = set(QUOTE_PRIORITY)
# SOL changes below this can be rent (new ATAs), tips and priority fees rather
# than a swap leg; only used where SOL is not the obvious quote.
SOL_DUST = Decimal("0.01")
# Multi-hop routes can leave a few raw units of an intermediate token behind.
TOKEN_DUST = Decimal("0.000001")

JUPITER = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
DEX_PROGRAMS: dict[str, str] = {
    JUPITER: "JUPITER",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "RAYDIUM",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "RAYDIUM_CPMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "RAYDIUM_CLMM",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "PUMP_AMM",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PUMPSWAP",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "ORCA",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "METEORA_DLMM",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "METEORA_DAMM_V2",
}


def _account_key(entry) -> str:
    return entry["pubkey"] if isinstance(entry, dict) else entry


def _signers(message: dict) -> list[str]:
    keys = message.get("accountKeys", [])
    if keys and isinstance(keys[0], dict):
        return [k["pubkey"] for k in keys if k.get("signer")]
    n = message.get("header", {}).get("numRequiredSignatures", 1)
    return [_account_key(k) for k in keys[:n]]


def _token_amount(bal_entry: dict) -> Decimal:
    """Exact human-unit amount: raw integer amount scaled by decimals."""
    ui = bal_entry.get("uiTokenAmount", {})
    raw, decimals = ui.get("amount"), ui.get("decimals")
    if raw is not None and decimals is not None:
        return Decimal(int(raw)).scaleb(-int(decimals))
    val = ui.get("uiAmountString")
    if val is None:
        val = ui.get("uiAmount")
    return Decimal(str(val)) if val is not None else Decimal(0)


def _token_deltas(meta: dict, owner: str) -> dict[str, Decimal]:
    """Net balance change per mint across all of owner's token accounts."""
    deltas: dict[str, Decimal] = {}
    for side, sign in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for entry in meta.get(side) or []:
            mint = entry.get("mint", "")
            if entry.get("owner") != owner:
                continue
            deltas[mint] = deltas.get(mint, Decimal(0)) + sign * _token_amount(entry)
    return {m: d for m, d in deltas.items() if d != 0}


def _infer_trader(meta: dict, fee_payer: str, signers: list[str]) -> str:
    """Pick the trading wallet when none is given.

    Relayer-paid txs have the relayer as fee payer and the trader as a
    co-signer that owns the token accounts being changed.
    """
    owners = {
        entry.get("owner")
        for side in ("preTokenBalances", "postTokenBalances")
        for entry in meta.get(side) or []
    }
    for signer in signers:
        if signer != fee_payer and signer in owners:
            return signer
    return fee_payer


def _detect_dex(tx: dict, mint: str = "") -> tuple[str, str]:
    """Return (program_id, source_name) from instructions.

    Only the outermost DEX calls count: an aggregator (e.g. Jupiter) invoking
    DEX legs is the source, not its legs. Among outermost calls -- e.g. a
    router doing USDC -> SOL on Raydium CLMM, then SOL -> token on PumpSwap --
    the first one touching ``mint`` wins, else the first one.
    """
    calls = [(1, ix) for ix in tx.get("transaction", {}).get("message", {}).get("instructions", [])]
    for group in tx.get("meta", {}).get("innerInstructions", []) or []:
        calls.extend((ix.get("stackHeight") or 2, ix) for ix in group.get("instructions", []))

    dex_calls = [(h, ix) for h, ix in calls if ix.get("programId", "") in DEX_PROGRAMS]
    if not dex_calls:
        return "", "UNKNOWN"
    top = min(h for h, _ in dex_calls)
    outer = [ix for h, ix in dex_calls if h == top]
    pid = next((ix["programId"] for ix in outer if mint and mint in ix.get("accounts", [])),
               outer[0]["programId"])
    return pid, DEX_PROGRAMS[pid]


def parse_swap(
    tx: dict,
    wallet: str | None = None,
    quote_mints: Iterable[str] | None = None,
) -> Swap | None:
    """Parse a single transaction into a Swap. Returns None if not a swap.

    wallet: the trader to parse for. When omitted, it is inferred: the
        non-fee-payer signer owning changed token accounts (relayer-paid tx),
        else the fee payer.
    quote_mints: quote assets in priority order; WSOL stands for native SOL.
        Defaults to USDC, USDT, SOL.
    """
    priority = tuple(quote_mints) if quote_mints is not None else QUOTE_PRIORITY
    meta = tx.get("meta")
    if not meta or meta.get("err") is not None:
        return None

    message = tx.get("transaction", {}).get("message", {})
    account_keys = [_account_key(k) for k in message.get("accountKeys", [])]
    if not account_keys:
        return None
    fee_payer = account_keys[0]
    trader = wallet if wallet is not None else _infer_trader(meta, fee_payer, _signers(message))
    if trader not in account_keys:
        return None
    trader_idx = account_keys.index(trader)

    # Native SOL change. The network fee is not part of the swap, but only the
    # fee payer pays it -- in relayer-paid txs the trader's balance never saw it.
    pre_balances = meta.get("preBalances", [])
    post_balances = meta.get("postBalances", [])
    lamports = 0
    if trader_idx < len(pre_balances) and trader_idx < len(post_balances):
        lamports = post_balances[trader_idx] - pre_balances[trader_idx]
        if trader == fee_payer:
            lamports += meta.get("fee", 0)

    # SOL leg = native + WSOL. Wrapping/unwrapping moves value between the two
    # and nets out; a persistent WSOL account can hold the whole swap leg.
    deltas = _token_deltas(meta, trader)
    sol = deltas.pop(WSOL, Decimal(0)) + Decimal(lamports).scaleb(-9)
    if WSOL in priority and sol:
        deltas[WSOL] = sol

    targets = {m: d for m, d in deltas.items() if m not in priority}
    swap_mint = ""
    quote_mint = ""
    if not targets:
        # Quote-to-quote (e.g. SOL -> USDC): the lower-priority asset is the one
        # traded. A SOL leg has to exceed rent/tip noise to count.
        moved = [m for m in priority if m in deltas and (m != WSOL or abs(deltas[m]) >= SOL_DUST)]
        if len(moved) != 2:
            return None
        quote_mint, swap_mint = moved
        targets = {swap_mint: deltas[swap_mint]}
    else:
        # Non-SOL quotes first: when a stablecoin moved, a small SOL change is
        # just rent/fees, not part of the swap.
        for mint in priority:
            if mint != WSOL and mint in deltas:
                quote_mint = mint
                break
    if not quote_mint:
        bought = [m for m in targets if targets[m] > 0]
        sold = [m for m in targets if targets[m] < 0]
        if len(bought) == 1 and len(sold) == 1 and deltas.get(WSOL, Decimal(0)) > -SOL_DUST:
            # Token-to-token: report it as buying the received token with the
            # sent one; the small SOL change is rent/tips. A bigger SOL outflow
            # means SOL was a leg too (e.g. adding liquidity), not this case.
            swap_mint, quote_mint = bought[0], sold[0]
        elif WSOL in deltas:
            quote_mint = WSOL
    if not quote_mint:
        return None
    if not swap_mint:
        swap_mint = max(targets, key=lambda m: abs(targets[m]))

    token_delta = targets[swap_mint]
    quote_delta = deltas[quote_mint]
    if token_delta > 0 and quote_delta < 0:
        direction = "BUY"
    elif token_delta < 0 and quote_delta > 0:
        direction = "SELL"
    else:
        return None

    # Liquidity ops move two assets the same way (both in on withdraw, both out
    # on deposit, e.g. closing a CLMM position); a swap has one asset per side.
    for mint, delta in targets.items():
        if mint not in (swap_mint, quote_mint) and (delta > 0) == (quote_delta > 0) \
                and abs(delta) >= TOKEN_DUST:
            return None

    quote_amount = float(abs(quote_delta))
    timestamp = tx.get("blockTime", 0)
    signature = (tx.get("transaction", {}).get("signatures") or [""])[0]
    program, source = _detect_dex(tx, swap_mint)

    return Swap(
        direction=direction,
        mint=swap_mint,
        symbol="",
        sol_amount=quote_amount if quote_mint == WSOL else 0.0,
        usdc_amount=quote_amount if quote_mint in STABLECOINS else 0.0,
        token_amount=float(abs(token_delta)),
        timestamp=timestamp,
        signature=signature,
        source=source,
        program=program,
        quote_mint=quote_mint,
        quote_amount=quote_amount,
        trader=trader,
        fee_payer=fee_payer,
    )


def parse_wallet(rpc: MultiRPC, wallet: str, limit: int = 300) -> list[Swap]:
    """Fetch signatures, batch-fetch transactions, parse swaps."""
    sig_infos = rpc.get_signatures(wallet, limit=limit)
    sigs = [s["signature"] for s in sig_infos]
    if not sigs:
        return []
    txs = rpc.batch_get_transactions(sigs, batch_size=10)
    results = []
    for tx in txs:
        if tx is None:
            continue
        swap = parse_swap(tx, wallet)
        if swap is not None:
            results.append(swap)
    return results


class SolanaParser:
    """Thin wrapper for convenient swap parsing."""

    def __init__(self, rpc: MultiRPC | None = None, resolver: TokenResolver | None = None):
        self._rpc = rpc or MultiRPC()
        self._resolver = resolver

    def _resolve_symbol(self, swap: Swap) -> Swap:
        if self._resolver:
            swap.symbol = self._resolver.resolve(swap.mint)
        return swap

    def parse_swap_by_sig(self, sig: str, wallet: str) -> Swap | None:
        """Fetch a transaction and parse it as a swap."""
        tx = self._rpc.get_transaction(sig)
        if tx is None:
            return None
        swap = parse_swap(tx, wallet)
        if swap is not None:
            self._resolve_symbol(swap)
        return swap

    def parse_wallet(self, wallet: str, limit: int = 300) -> list[Swap]:
        """Parse a wallet's recent swap history."""
        swaps = parse_wallet(self._rpc, wallet, limit=limit)
        for swap in swaps:
            self._resolve_symbol(swap)
        return swaps
