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
         [dRPC]      [Alchemy]     [Helius]     ← free tier providers
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │ getTransaction │  ← standard Solana RPC
                    │ (jsonParsed)   │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   Parser    │  ← balance-diff logic
                    │             │
                    │ pre/post    │
                    │ Balances    │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  Swap Data  │  → {direction, mint, sol_amount, ...}
                    └─────────────┘
```

## Solana Module Design

### parser.py — Core Swap Parser

Input: Raw `getTransaction` response (jsonParsed encoding)

Processing:
1. Identify fee payer from `accountKeys[0]`
2. Compute SOL change: `(postBalances[i] - preBalances[i] + fee) / 1e9`
3. Compute token changes from `preTokenBalances` / `postTokenBalances`:
   - Match by `accountIndex` to find wallet's token accounts
   - Calculate delta for each mint
4. Classify:
   - SOL decreased + token increased → BUY
   - SOL increased + token decreased → SELL
   - USDC/USDT decreased + token increased → BUY (stablecoin pair)
   - USDC/USDT increased + token decreased → SELL (stablecoin pair)
5. Extract amounts, mint address, timestamp, signature

Output:
```python
{
    "direction":    "BUY" | "SELL",
    "mint":         "TokenMintAddress...",
    "symbol":       "BONK",               # resolved via metadata
    "sol_amount":   0.5,                   # SOL spent/received
    "usdc_amount":  0.0,                   # USDC spent/received (if stablecoin pair)
    "token_amount": 1000000.0,             # tokens received (BUY) or sent (SELL)
    "timestamp":    1695849600,
    "signature":    "5abc123...",
    "program":      "JUP6Lkb...",          # DEX program ID
    "source":       "JUPITER",             # human-readable DEX name
}
```

### rpc.py — Multi-RPC Client

Features:
- Round-robin rotation across providers
- Automatic failover on 429/500 errors
- Per-provider rate limiting (configurable)
- Batch RPC support (multiple calls in one HTTP request)
- Health check & provider scoring

```python
class MultiRPC:
    def __init__(self, endpoints: list[str]):
        ...

    def get_transaction(self, sig: str) -> dict:
        """Fetch with automatic rotation and retry."""

    def get_signatures(self, address: str, limit: int) -> list[str]:
        """Fetch signatures with pagination."""

    def batch_get_transactions(self, sigs: list[str], batch_size: int = 10) -> list[dict]:
        """Batch fetch with rate limiting."""
```

### metadata.py — Token Metadata Resolver

Resolve mint addresses to symbols and decimals:
- Cache results in memory + local file
- Primary: Solana token metadata program (on-chain)
- Fallback: Jupiter token list API (free, no auth)

### compat.py — Helius Compatibility Layer (Optional)

For projects migrating from Helius Enhanced API:
```python
from dexray.solana.compat import to_helius_format

raw_tx = rpc.get_transaction(sig)
swap = parser.parse_swap(raw_tx, wallet)
helius_like = to_helius_format(swap)
# => same structure as Helius Enhanced Transaction response
```

## Edge Cases & Handling

| Scenario | Handling |
|---|---|
| Multi-hop swap (A→B→C) | Balance-diff captures net result automatically |
| Partial fill | Treated as normal swap with actual amounts |
| Failed transaction | `meta.err` is not null → skip |
| Wrap/Unwrap SOL | SOL ↔ WSOL, detect via WSOL mint address |
| Token-to-token (no SOL) | Detect as two token balance changes |
| Multiple swaps in one tx | Return list of swaps (rare but possible) |
| Airdrop / transfer (not swap) | Only SOL or only token changes → not a swap → skip |

## Performance Targets

| Metric | Target |
|---|---|
| Parse latency (single tx) | < 5ms (CPU only, no I/O) |
| RPC fetch + parse | < 200ms per transaction |
| Batch throughput | 500+ tx/min with 3 free RPC providers |
| Wallet scan (300 sigs) | < 60 seconds |
| Memory usage | < 50MB for 10,000 tx cache |
