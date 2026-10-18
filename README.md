# DexRay — Free Solana DEX Swap Parser

**Parse BUY/SELL swaps from Jupiter, Raydium, Pump.fun, Orca, Meteora — using free standard RPC. Drop-in Helius Enhanced API replacement.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-155%20passed-brightgreen.svg)](#testing)

[English](README.md) | [中文](README_CN.md) | [日本語](README_JA.md) | [한국어](README_KO.md)

---

DexRay is a Python library that parses **any Solana DEX swap** into structured data (BUY/SELL, token, amount, PnL) using only free standard RPC calls. It works by comparing `preTokenBalances` vs `postTokenBalances` — no Helius Enhanced API, no paid subscription, no vendor lock-in.

**Use cases:** trading bots, wallet analyzers, portfolio trackers, copy-trading, smart money analysis, on-chain analytics.

> **Why Solana only?** EVM chains have standardized Event Logs — any free RPC can parse swaps trivially. Solana is the only major chain where swap parsing requires either a paid API (Helius $49+/mo) or building your own parser. DexRay is that parser — free and open source.

## Why DexRay?

| | Helius Enhanced API | DexRay |
|---|---|---|
| Cost | $49+/mo | **Free** (standard RPC) |
| Rate limit | 10-50 req/s | **Unlimited** (multi-RPC rotation) |
| Vendor lock-in | Helius only | **Any Solana RPC** |
| Setup | API key required | **Zero config** |
| Open source | No | **Yes** |

## Quick Start

### Install

```bash
pip install git+https://github.com/0788lance-lab/dexray.git
```

### Parse a swap in 2 lines

```python
from dexray import SolanaParser

parser = SolanaParser()  # zero config — uses free Solana public RPC

# Parse a real Jupiter swap (copy-paste this to verify it works)
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
print(swap)
# => Swap(direction='BUY', sol_amount=0.03, token_amount=12899.01, source='JUPITER', ...)
```

### More examples

```python
# Parse a PumpSwap buy
swap = parser.parse_swap_by_sig(
    "3GnMkq8ozGkn2eMRSF7fLykRkwHmtDWxA9U1PHBeKsTU73pjUstQdNWqEhcyYZkTkd7VM7GzJGpJze6vDQxoTQpH",
    wallet="Fdg75QBKQ7UMMM4hrthGXxYvRCT5qtRAd8hnaXNGqs2K",
)
# => Swap(direction='BUY', sol_amount=1.01, token_amount=194259.73, source='PUMPSWAP', ...)

# Parse a Raydium sell
swap = parser.parse_swap_by_sig(
    "5s17quVEjwJHtqtMZTo7Q6PLNwJQb3gnUnAhEd1y3p5e3MoWM5Nt7ZbqsZzWgCbWZRaeJ4Yb941BSfUpCuUr6pUM",
    wallet="6M1RhUfjmojYcY6QXqsDb1geG6Tpz8bzH2C8DRzzY8be",
)
# => Swap(direction='SELL', sol_amount=3.26, token_amount=460016.10, source='RAYDIUM_CPMM', ...)

# Batch parse a wallet's recent trades
trades = parser.parse_wallet("85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7", limit=50)
for t in trades:
    print(f"{t.direction} {t.symbol or t.mint[:8]} | {t.sol_amount:.4f} SOL")
```

## How It Works

Instead of relying on proprietary "enhanced" transaction parsing, DexRay reads the **result** of any swap:

```
Raw Transaction (getTransaction RPC)
  → Compare preTokenBalances vs postTokenBalances
  → Detect token flow direction
  → SOL/USDC/USDT out + token in = BUY
  → token out + SOL/USDC/USDT in = SELL
```

Amounts come from the raw integer balances (no float drift), and the trader is the
signing wallet, not the fee payer, so relayer-paid ("gasless") swaps are attributed
correctly.

This works **regardless of which DEX** was used — Jupiter, Raydium, Pump.fun, Orca, Meteora, or any future DEX — because we read balance changes, not program-specific instructions.

## Features

- **Zero config** — works out of the box with Solana public RPC, no API keys needed
- **Multi-RPC rotation** — add multiple free RPC providers for higher throughput
- **Universal DEX support** — Jupiter, Raydium, Pump.fun, Orca, Meteora, and any future DEX
- **Any quote asset** — SOL, USDC, USDT, token-to-token; `quote_mint` + `quote_amount` on every swap
- **Relayer-aware** — `trader` (signer) and `fee_payer` reported separately
- **All tx versions** — legacy, v0 and v1 transactions
- **Live quality check** — `python -m dexray check` scores the parser against real mainnet swaps
- **Token metadata** — resolve mint addresses to symbols via Jupiter token list
- **Batch processing** — efficient bulk transaction parsing with rate limiting
- **Helius compatible** — optional compatibility layer for easy migration

## Supported DEXes

| DEX | Program | Detection |
|-----|---------|-----------|
| Jupiter V6 | `JUP6Lkb...` | ✅ |
| Raydium V4 | `675kPX9...` | ✅ |
| Raydium CPMM | `CPMMoo8...` | ✅ |
| Raydium CLMM | `CAMMCzo...` | ✅ |
| Pump.fun AMM | `6EF8rre...` | ✅ |
| PumpSwap | `pAMMBay...` | ✅ |
| Orca Whirlpool | `whirLbM...` | ✅ |
| Meteora DLMM | `LBUZKhR...` | ✅ |
| Meteora DAMM V2 | `cpamdpZ...` | ✅ |
| *Any other DEX* | *Any* | ✅ (detected as UNKNOWN) |

> Swap detection works for **all** DEXes. The table above only affects the `source` label.

## Recommended RPC Providers

DexRay works with **any** Solana RPC. Below are tested free providers (as of Sep 2026):

### No signup required

| Provider | URL | Rate limit |
|----------|-----|------------|
| Solana Public | `https://api.mainnet-beta.solana.com` | ~5 RPS |
| SolanaTracker | `https://rpc.solanatracker.io/public` | Unknown |
| PublicNode | `https://solana-rpc.publicnode.com` | Unknown |

### Free with signup (no credit card)

| Provider | Free quota | Signup |
|----------|-----------|--------|
| **Alchemy** (recommended) | 30M CU/month, 25 RPS | [alchemy.com](https://www.alchemy.com) |
| **Chainstack** | 3M requests/month, 25 RPS | [chainstack.com](https://chainstack.com) |
| **Helius** | 1M credits/month, 10 RPS | [helius.dev](https://helius.dev) |

### Known issues

| Provider | Issue |
|----------|-------|
| dRPC | Free plan does **not** support Solana (EVM only) |
| Ankr | Only 16h transaction history — unusable for wallet analysis |

### Recommended setup (production)

```python
from dexray import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",     # Alchemy (primary)
    "https://solana-mainnet.core.chainstack.com/YOUR_KEY",   # Chainstack (backup)
    "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",      # Helius (backup)
    "https://api.mainnet-beta.solana.com",                    # Public (fallback)
])

parser = SolanaParser(rpc)
```

## Advanced Usage

### Rate limiting per provider

```python
rpc = MultiRPC([
    {"url": "https://api.mainnet-beta.solana.com", "rps": 5},
    {"url": "https://solana-mainnet.g.alchemy.com/v2/KEY", "rps": 25},
])
```

### Token symbol resolution

```python
from dexray import SolanaParser, TokenResolver

resolver = TokenResolver()  # auto-loads Jupiter token list
parser = SolanaParser(resolver=resolver)

swap = parser.parse_swap_by_sig(sig, wallet=addr)
print(swap.symbol)  # => "BONK" (instead of raw mint address)
```

### Low-level parsing (no RPC)

```python
from dexray import parse_swap

# If you already have the raw transaction dict from getTransaction:
swap = parse_swap(raw_tx, wallet="your_wallet_address")

# No wallet: the trader is inferred (the signing wallet, even when a relayer paid the fee)
swap = parse_swap(raw_tx)
```

### Helius migration

```python
from dexray import to_helius_format, parse_swap

swap = parse_swap(raw_tx, wallet)
helius_like = to_helius_format(swap)
# => Same structure as Helius Enhanced Transaction response
```

See [Migration Guide](docs/MIGRATION.md) for detailed field mapping.

## API Reference

### `SolanaParser(rpc=None, resolver=None)`

Main entry point. Uses free Solana public RPC by default.

| Method | Description |
|--------|-------------|
| `parse_swap_by_sig(sig, wallet)` | Fetch and parse a single transaction |
| `parse_wallet(wallet, limit=300)` | Parse a wallet's recent swap history |

### `parse_swap(tx, wallet=None, quote_mints=None) → Swap | None`

Pure function. Parse a raw `getTransaction` response into a `Swap`. Returns `None` if the transaction is not a swap.

- `wallet` — trader to parse for. Omit it to infer the trader: the co-signer that owns the changed token accounts when a relayer paid the fee, otherwise the fee payer.
- `quote_mints` — quote assets in priority order (default USDC, USDT, SOL, with the WSOL mint standing for SOL). A swap between two non-quote tokens is reported as buying the received token with the sent one.

### `Swap` fields

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `str` | `"BUY"` or `"SELL"` |
| `mint` | `str` | Token mint address |
| `symbol` | `str` | Token symbol (if resolver is used) |
| `sol_amount` | `float` | SOL spent (BUY) or received (SELL); 0 if the quote isn't SOL |
| `usdc_amount` | `float` | USDC/USDT amount (if stablecoin pair); prefer `quote_amount` |
| `token_amount` | `float` | Token amount received (BUY) or sent (SELL) |
| `timestamp` | `int` | Unix timestamp |
| `signature` | `str` | Transaction signature |
| `source` | `str` | DEX name (e.g., `"JUPITER"`, `"RAYDIUM"`) |
| `program` | `str` | DEX program address |
| `quote_mint` | `str` | Asset paid (BUY) or received (SELL); WSOL mint for SOL |
| `quote_amount` | `float` | `quote_mint` amount in human units |
| `trader` | `str` | Wallet whose balances were parsed |
| `fee_payer` | `str` | `accountKeys[0]`; differs from `trader` for relayer-paid txs |

### `MultiRPC(endpoints=None, max_retries=3, timeout=30.0)`

| Method | Description |
|--------|-------------|
| `get_transaction(sig)` | Fetch a single transaction |
| `get_signatures(address, limit)` | Fetch recent signatures for an address |
| `batch_get_transactions(sigs, batch_size=10)` | Batch fetch transactions |

### `TokenResolver(preload=True, cache_file=None)`

| Method | Description |
|--------|-------------|
| `resolve(mint)` | Get symbol for a mint address |
| `batch_resolve(mints)` | Resolve multiple mints |
| `add(mint, symbol)` | Manually add a mapping |

## Project Structure

```
dexray/
├── dexray/
│   ├── __init__.py          # Package exports
│   ├── core.py              # Swap dataclass
│   └── solana/
│       ├── __init__.py
│       ├── parser.py        # Swap parser (balance-diff approach)
│       ├── rpc.py           # Multi-RPC client with rotation
│       ├── metadata.py      # Token symbol resolver
│       ├── compat.py        # Helius compatibility layer
│       └── quality.py       # Live data-quality check
├── scripts/
│   └── add_fixture.py       # Save a mainnet tx as a regression fixture
├── tests/
│   ├── test_parser.py       # Parser unit tests
│   ├── test_rpc.py          # RPC client tests
│   ├── test_metadata.py     # Metadata resolver tests
│   ├── test_integration.py  # Real transaction integration tests
│   ├── test_compat.py       # Helius compat tests
│   ├── test_regression.py   # Real txs the parser once got wrong
│   ├── test_quality.py      # Quality checker tests
│   └── fixtures/            # Real mainnet transaction samples
├── docs/
│   ├── ARCHITECTURE.md      # Technical design
│   ├── DEVELOPMENT.md       # Development guide
│   ├── QUALITY.md           # Data-quality check and baseline
│   └── MIGRATION.md         # Helius migration guide
├── pyproject.toml
├── LICENSE
└── README.md
```

## Testing

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e ".[dev]"
pytest tests/ -v
```

155 tests covering: Jupiter, Raydium, PumpSwap, USDC pairs, relayer-paid swaps, v0/v1/legacy transactions, failed transactions, ATA creation/closure, and more.
`tests/test_regression.py` replays real mainnet transactions the parser once got wrong; every parser fix adds one (see [CONTRIBUTING](CONTRIBUTING.md)).

### Live data-quality check

```bash
python -m dexray check --per-dex 50
```

Samples recent swaps for every supported DEX, parses them, and checks direction and amounts against the raw on-chain balance changes. Exits non-zero and alerts (Telegram/Slack, optional) when a DEX drops below 98%. Runs weekly in CI. See [docs/QUALITY.md](docs/QUALITY.md).

## Contributing

Contributions welcome! See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development setup.

1. Fork the repo
2. Create a feature branch
3. Add tests for your changes
4. Submit a PR

## License

[MIT](LICENSE)
