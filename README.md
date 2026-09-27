# DexRay

**Decode Solana DEX swaps from raw transactions. No paid APIs required.**

DexRay is a lightweight, open-source Solana transaction parser that extracts structured swap data (BUY/SELL, token, amount, PnL) directly from standard RPC responses — no Helius Enhanced API, no vendor lock-in.

> **Why Solana only?** EVM chains have standardized Event Logs — any free RPC can parse swaps trivially. Solana is the only major chain where swap parsing requires either a paid proprietary API (Helius) or building your own parser. That's what DexRay does.

## Why DexRay?

Every Solana trading bot, portfolio tracker, and wallet analyzer needs to parse DEX swaps. Most depend on paid APIs like Helius Enhanced Transactions ($49+/mo) which have strict rate limits. DexRay removes that dependency:

| | Helius Enhanced API | DexRay |
|---|---|---|
| Cost | $49+/mo for reasonable limits | **Free** (uses standard RPC) |
| Rate limit | 10-50 req/s (paid tier) | **Unlimited** (multi-RPC rotation) |
| Vendor lock-in | Helius only | **Any Solana RPC provider** |
| Accuracy | High | **High** (pre/postTokenBalances approach) |
| Open source | No | **Yes** |

## How It Works

Instead of relying on proprietary "enhanced" transaction parsing, DexRay uses a simple but robust approach:

1. Fetch raw transaction via standard `getTransaction` RPC (works with ANY provider)
2. Compare `preTokenBalances` vs `postTokenBalances` to detect token flow
3. Compare `preBalances` vs `postBalances` to detect SOL/native token flow
4. Determine swap direction: SOL out + token in = **BUY**, token out + SOL in = **SELL**

This works **regardless of which DEX** was used (Jupiter, Raydium, Pump.fun, Orca, etc.) because we're reading the result, not parsing program-specific instructions.

## Features

- **Zero-dependency parsing** — no paid API keys needed
- **Multi-RPC rotation** — distribute load across free providers (dRPC, Alchemy, Helius free, etc.)
- **Universal DEX support** — Jupiter, Raydium, Pump.fun, Orca, Meteora, DFlow, and any future DEX
- **USDC/USDT swaps** — handles stablecoin quote pairs, not just SOL
- **Token metadata** — resolve mint addresses to symbols via on-chain metadata
- **Batch processing** — efficient bulk transaction parsing with rate limiting
- **Drop-in replacement** — API-compatible with Helius Enhanced Transaction format (optional)

## Quick Start

```python
from dexray.solana import SolanaParser, MultiRPC

# Set up with multiple free RPC providers
rpc = MultiRPC([
    "https://api.mainnet-beta.solana.com",              # Solana public
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY", # Alchemy free
    "https://lb.drpc.org/ogrpc?network=solana&dkey=KEY", # dRPC free
])

parser = SolanaParser(rpc)

# Parse a single transaction
swap = parser.parse_swap("5abc123...signature", wallet="DfUwJCaf...")
# => {"direction": "BUY", "mint": "...", "sol_amount": 0.5, "token_amount": 1000000, ...}

# Batch parse a wallet's recent trades
trades = parser.parse_wallet("DfUwJCaf...", limit=100)
for t in trades:
    print(f"{t['direction']} {t['symbol']} | {t['sol_amount']:.4f} SOL")
```

## Installation

```bash
pip install dexray
```

Or from source:

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e .
```

## Project Structure

```
dexray/
├── dexray/
│   ├── __init__.py          # Package entry point
│   ├── core.py              # Shared types & interfaces
│   ├── solana/
│   │   ├── __init__.py
│   │   ├── parser.py        # Swap parser (pre/postTokenBalances approach)
│   │   ├── rpc.py           # Multi-RPC client with rotation & retry
│   │   ├── metadata.py      # Token symbol/decimals resolver
│   │   └── compat.py        # Helius Enhanced API compatible output (optional)
├── tests/
│   ├── test_parser.py
│   ├── test_rpc.py
│   └── fixtures/            # Real transaction samples for testing
├── examples/
│   ├── parse_wallet.py      # Parse a wallet's trading history
│   ├── live_monitor.py      # WebSocket live trade monitor
│   └── migrate_helius.py    # Migration guide from Helius
├── docs/
│   ├── ARCHITECTURE.md      # Technical design & decisions
│   ├── DEVELOPMENT.md       # Developer guide
│   └── MIGRATION.md         # Helius → DexRay migration guide
├── README.md
├── setup.py
├── pyproject.toml
└── LICENSE
```

## Contributing

Contributions welcome! See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup and guidelines.

## License

MIT
