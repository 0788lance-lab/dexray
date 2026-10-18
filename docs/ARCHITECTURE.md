# DexRay Architecture

## Design Philosophy

1. **Standard RPC only** — never depend on proprietary "enhanced" APIs
2. **Balance-diff approach** — read results (pre/post balances), don't parse instructions
3. **Multi-provider** — rotate across free RPC providers to maximize throughput
4. **Solana-focused** — the only major chain where free swap parsing is a real gap

## Core Concepts

### Swap Detection via Balance Diff

Traditional approach (Helius Enhanced API):
```
Transaction → Parse program instructions → Identify DEX-specific swap format → Extract data
```
Problem: Every DEX has different instruction layouts. Must maintain parsers for each.

DexRay approach:
```
Transaction → Compare preBalances vs postBalances → Detect token flow → Determine direction
```
Advantage: Works for ANY DEX, past and future. The Solana runtime guarantees accurate balance reporting.

### Data Flow

```
                    ┌─────────────┐
User Request  ───→  │  MultiRPC   │  ← rotates across providers
                    │  Client     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        [Alchemy]   [Chainstack]   [Solana]    ← free tier providers
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌──────────────┐
                    │getTransaction│  ← standard Solana RPC
                    │ (jsonParsed) │
                    └──────┬───────┘
                           ▼
                    ┌─────────────┐
                    │   Parser    │  ← balance-diff logic
                    │  pre/post   │
                    │  Balances   │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  Swap Data  │  → Swap(direction, mint, sol_amount, ...)
                    └─────────────┘
```

## Module Design

### parser.py — Core Swap Parser

Input: Raw `getTransaction` response (jsonParsed encoding, `maxSupportedTransactionVersion: 1`)

Processing:
1. Check `meta.err` — skip failed transactions
2. Resolve the trader: the given `wallet`, or inferred — a non-fee-payer signer that owns changed token accounts (relayer-paid tx), else the fee payer (`accountKeys[0]`)
3. SOL leg: native `postBalances[i] - preBalances[i]`, plus the fee only if the trader paid it, plus the trader's WSOL token balance change (wrap/unwrap nets out; persistent WSOL accounts are counted)
4. Token changes from `preTokenBalances` / `postTokenBalances`:
   - Match by `owner`, sum all of the trader's accounts per mint
   - Exact amounts from raw integer `amount` + `decimals` (no `uiAmount` float noise)
   - Handle asymmetric pre/post (new ATA only in post, closed ATA only in pre)
5. Pick the quote asset (priority USDC > USDT > SOL, configurable):
   - A stablecoin moved → it is the quote; small SOL changes are rent/fees
   - Exactly one token in and one out, SOL outflow under 0.01 → token-to-token, sent token is the quote
   - Otherwise SOL is the quote
   - Only quote assets moved (e.g. SOL → USDC) → the lower-priority one is traded, the higher-priority one is the quote
6. Direction: token in + quote out → BUY; token out + quote in → SELL
   - Another token moving the same way as the quote (two assets in, or two out) → liquidity op, not a swap
7. Identify DEX from the outermost DEX calls (lowest `stackHeight`; an aggregator wrapping its legs wins): the first one whose accounts include the token mint (the leg that delivered it), else the first one

Output: `Swap` dataclass or `None` (if not a detectable swap)

### rpc.py — Multi-RPC Client

```python
class MultiRPC:
    def __init__(self, endpoints=None):  # defaults to Solana public RPC
        ...

    def get_transaction(self, sig: str) -> dict | None:
    def get_signatures(self, address: str, limit: int) -> list[dict]:
    def batch_get_transactions(self, sigs: list[str], batch_size: int = 10) -> list[dict | None]:
```

Features:
- Round-robin rotation across providers
- Automatic failover on 429/500/502/503 errors
- Exponential backoff after all providers fail
- Per-provider rate limiting (configurable RPS)
- Batch JSON-RPC support (multiple calls in one HTTP request)

### metadata.py — Token Metadata Resolver

Resolve mint addresses to symbols:
- Memory cache + local file cache (`~/.dexray/token_cache.json`)
- Preload: Jupiter strict token list (~1000 verified tokens)
- Lazy fallback: Jupiter all-tokens list (loaded once on first cache miss)

### compat.py — Helius Compatibility Layer (Optional)

```python
from dexray import to_helius_format

helius_like = to_helius_format(swap)
# => Same structure as Helius Enhanced Transaction response
```

## Edge Cases & Handling

| Scenario | Handling |
|---|---|
| Multi-hop swap (A→B→C) | Balance-diff captures net result automatically |
| Partial fill | Treated as normal swap with actual amounts |
| Failed transaction | `meta.err` is not null → skip |
| Wrap/Unwrap SOL | WSOL merged into the SOL leg; wrap/unwrap nets out |
| Relayer-paid (gasless) tx | Trader = signer, fee not deducted from trader; `fee_payer` reported separately |
| Version 1 tx | Fetched with `maxSupportedTransactionVersion: 1` (version 0 makes the RPC refuse them) |
| USDC/USDT pair | Stablecoin takes priority over small SOL fee changes |
| First buy (new ATA) | Token only in postTokenBalances → handled via union merge |
| Full sell (ATA closed) | Token only in preTokenBalances → handled via union merge |
| Airdrop / transfer | Only SOL or only token changes → not a swap → skip |

## Performance Targets

| Metric | Target |
|---|---|
| Parse latency (single tx) | < 5ms (CPU only, no I/O) |
| RPC fetch + parse | < 200ms per transaction |
| Batch throughput | 500+ tx/min with 3 free RPC providers |
| Wallet scan (300 sigs) | < 60 seconds |
