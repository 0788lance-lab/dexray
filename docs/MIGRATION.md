# Helius Enhanced API -> DexRay Migration Guide

## Overview

This guide helps projects currently using Helius Enhanced Transactions API migrate to DexRay for free, unlimited swap parsing.

## What Changes

| Before (Helius) | After (DexRay) |
|---|---|
| `POST api.helius.xyz/v0/transactions` | `getTransaction` via any RPC |
| Helius-specific JSON response | Standard Solana RPC response → DexRay parser |
| Single provider, rate limited | Multi-provider, rotation |
| $49+/mo for production use | Free |

## Step-by-Step Migration

### 1. Install DexRay

```bash
pip install dexray
```

### 2. Set Up Multi-RPC

```python
from dexray.solana import MultiRPC

# Replace your single Helius key with multiple free providers
rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY",     # Alchemy (primary)
    "https://solana-mainnet.core.chainstack.com/YOUR_CHAINSTACK_KEY", # Chainstack
    "https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY",       # keep as one of many
    "https://api.mainnet-beta.solana.com",                            # public fallback
])
```

### 3. Replace Enhanced API Calls

#### Parsing a single transaction

```python
# BEFORE: Helius Enhanced API
import requests
ENHANCED_URL = f"https://api.helius.xyz/v0/transactions/?api-key={KEY}"
response = requests.post(ENHANCED_URL, json={"transactions": [signature]})
enhanced_tx = response.json()[0]
# Parse enhanced_tx manually...

# AFTER: DexRay
from dexray.solana import SolanaParser
parser = SolanaParser(rpc)
swap = parser.parse_swap_by_sig(signature, wallet="YourWallet...")
# swap = {"direction": "BUY", "mint": "...", "sol_amount": 0.5, ...}
```

#### Parsing a wallet's history

```python
# BEFORE: Helius
sigs = get_signatures(wallet, limit=300)  # Helius RPC
for batch in chunks(sigs, 100):
    response = requests.post(ENHANCED_URL, json={"transactions": batch})
    for tx in response.json():
        swap = parse_helius_swap(tx, wallet)  # your custom parser

# AFTER: DexRay
trades = parser.parse_wallet(wallet, limit=300)
# trades = [{"direction": "BUY", ...}, {"direction": "SELL", ...}, ...]
```

### 4. Field Mapping

If your code reads specific Helius Enhanced fields:

| Helius Field | DexRay Equivalent |
|---|---|
| `tx["type"]` | Always "SWAP" (non-swaps are filtered) |
| `tx["source"]` | `swap["source"]` (e.g., "JUPITER") |
| `tx["events"]["swap"]["nativeInput"]` | `swap["sol_amount"]` |
| `tx["tokenTransfers"][n]["mint"]` | `swap["mint"]` |
| `tx["tokenTransfers"][n]["tokenAmount"]` | `swap["token_amount"]` |
| `tx["timestamp"]` | `swap["timestamp"]` |
| `tx["signature"]` | `swap["signature"]` |
| `tx["description"]` | Not provided (use `swap["symbol"]` instead) |
| `tx["accountData"][n]["nativeBalanceChange"]` | Computed internally |

### 5. Helius Compatibility Mode (Optional)

If you have extensive code built around Helius response format:

```python
from dexray.solana.compat import to_helius_format

raw_tx = rpc.get_transaction(sig)
helius_like = to_helius_format(raw_tx, wallet)
# => Same structure as Helius Enhanced Transaction
# Your existing parse_helius_swap() will work unchanged
```

## Verification

Run both parsers in parallel to verify identical results:

```python
from dexray.solana import SolanaParser, MultiRPC

rpc = MultiRPC([...])
parser = SolanaParser(rpc)

# Compare for 100 transactions
sigs = rpc.get_signatures(wallet, limit=100)
mismatches = 0
for sig in sigs:
    dexray_swap = parser.parse_swap_by_sig(sig, wallet)
    helius_swap = your_existing_helius_parse(sig)
    if dexray_swap and helius_swap:
        if dexray_swap["direction"] != helius_swap["direction"]:
            print(f"MISMATCH: {sig}")
            mismatches += 1

print(f"Mismatches: {mismatches}/{len(sigs)}")
```

## FAQ

**Q: Will DexRay work with my existing Helius WebSocket subscription?**
A: WebSocket subscriptions use standard Solana `accountSubscribe`, not Enhanced API. They work with any RPC provider. DexRay only replaces the transaction parsing part.

**Q: What about Helius DAS API / Priority Fee API?**
A: DexRay only replaces Enhanced Transactions parsing. If you use other Helius APIs, those are separate concerns.

**Q: Is the parsing accuracy the same?**
A: Yes. The balance-diff approach captures the exact same information. In some edge cases (complex multi-hop swaps), DexRay may actually be more accurate because it reads the final result rather than trying to interpret intermediate steps.
