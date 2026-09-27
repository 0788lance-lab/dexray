"""Core swap parser: detect BUY/SELL from pre/postTokenBalances diff."""

from __future__ import annotations

from dexray.core import Swap
from dexray.solana.rpc import MultiRPC
from dexray.solana.metadata import TokenResolver

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
LAMPORTS_PER_SOL = 1_000_000_000
QUOTE_MINTS = {WSOL, USDC, USDT}

DEX_PROGRAMS: dict[str, str] = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "JUPITER",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "RAYDIUM",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "RAYDIUM_CPMM",
    "CAMMCzo5YL8w4VFF8KVHr7Wfao2BjNrHsgzb5i4Qi6Mc": "RAYDIUM_CLMM",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "PUMP_AMM",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PUMPSWAP",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "ORCA",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "METEORA_DLMM",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "METEORA_DAMM_V2",
}


def _account_key(entry) -> str:
    return entry["pubkey"] if isinstance(entry, dict) else entry


def _token_amount(bal_entry: dict) -> float:
    ui = bal_entry.get("uiTokenAmount", {})
    val = ui.get("uiAmount")
    if val is not None:
        return float(val)
    s = ui.get("uiAmountString", "0")
    return float(s)


def _detect_dex(tx: dict) -> tuple[str, str]:
    """Return (program_id, source_name) from instructions."""
    instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
    for ix in instructions:
        pid = ix.get("programId", "")
        if pid in DEX_PROGRAMS:
            return pid, DEX_PROGRAMS[pid]

    inner = tx.get("meta", {}).get("innerInstructions", []) or []
    for group in inner:
        for ix in group.get("instructions", []):
            pid = ix.get("programId", "")
            if pid in DEX_PROGRAMS:
                return pid, DEX_PROGRAMS[pid]

    return "", "UNKNOWN"


def parse_swap(
    tx: dict,
    wallet: str,
    quote_mints: set[str] | None = None,
) -> Swap | None:
    """Parse a single transaction into a Swap. Returns None if not a swap."""
    if quote_mints is None:
        quote_mints = QUOTE_MINTS
    meta = tx.get("meta")
    if not meta or meta.get("err") is not None:
        return None

    # Find wallet index in accountKeys
    account_keys = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
    wallet_idx = None
    for i, key in enumerate(account_keys):
        if _account_key(key) == wallet:
            wallet_idx = i
            break
    if wallet_idx is None:
        return None

    # SOL change (add back fee since fee isn't part of the swap)
    pre_balances = meta.get("preBalances", [])
    post_balances = meta.get("postBalances", [])
    fee = meta.get("fee", 0)
    sol_change = 0.0
    if wallet_idx < len(pre_balances) and wallet_idx < len(post_balances):
        sol_change = (post_balances[wallet_idx] - pre_balances[wallet_idx] + fee) / LAMPORTS_PER_SOL

    # Token changes -- build {mint: amount} for pre and post
    pre_tokens: dict[str, float] = {}
    post_tokens: dict[str, float] = {}

    for entry in meta.get("preTokenBalances", []):
        owner = entry.get("owner", "")
        mint = entry.get("mint", "")
        if owner == wallet and mint != WSOL:
            pre_tokens[mint] = _token_amount(entry)

    for entry in meta.get("postTokenBalances", []):
        owner = entry.get("owner", "")
        mint = entry.get("mint", "")
        if owner == wallet and mint != WSOL:
            post_tokens[mint] = _token_amount(entry)

    # Compute deltas for all mints seen
    all_mints = set(pre_tokens.keys()) | set(post_tokens.keys())
    token_deltas: dict[str, float] = {}
    for mint in all_mints:
        pre_val = pre_tokens.get(mint, 0.0)
        post_val = post_tokens.get(mint, 0.0)
        delta = post_val - pre_val
        if delta != 0.0:
            token_deltas[mint] = delta

    # Separate quote and non-quote token changes
    stablecoin_mints = {USDC, USDT}
    quote_delta: dict[str, float] = {}
    target_delta: dict[str, float] = {}

    for mint, delta in token_deltas.items():
        if mint in stablecoin_mints:
            quote_delta[mint] = delta
        else:
            target_delta[mint] = delta

    # Determine swap direction
    direction = None
    swap_mint = ""
    swap_token_amount = 0.0
    swap_sol_amount = abs(sol_change)
    swap_usdc_amount = 0.0

    if target_delta:
        # Pick the target token (largest absolute change if multiple)
        swap_mint = max(target_delta, key=lambda m: abs(target_delta[m]))
        swap_token_amount = abs(target_delta[swap_mint])
        token_increased = target_delta[swap_mint] > 0

        # Check stablecoin pair first -- when a stablecoin changed significantly,
        # any small SOL change is just fee compensation, not part of the swap.
        total_quote = sum(quote_delta.values()) if quote_delta else 0.0
        if quote_delta and abs(total_quote) > 1e-6:
            if total_quote < 0 and token_increased:
                direction = "BUY"
                swap_sol_amount = 0.0
                swap_usdc_amount = abs(total_quote)
            elif total_quote > 0 and not token_increased:
                direction = "SELL"
                swap_sol_amount = 0.0
                swap_usdc_amount = abs(total_quote)
        elif sol_change < -1e-9 and token_increased:
            direction = "BUY"
        elif sol_change > 1e-9 and not token_increased:
            direction = "SELL"

    if direction is None:
        return None

    timestamp = tx.get("blockTime", 0)
    signature = (tx.get("transaction", {}).get("signatures") or [""])[0]
    program, source = _detect_dex(tx)

    return Swap(
        direction=direction,
        mint=swap_mint,
        symbol="",
        sol_amount=swap_sol_amount,
        usdc_amount=swap_usdc_amount,
        token_amount=swap_token_amount,
        timestamp=timestamp,
        signature=signature,
        source=source,
        program=program,
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

    def __init__(self, rpc: MultiRPC, resolver: TokenResolver | None = None):
        self._rpc = rpc
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
