# DexRay Development Guide

## Setup

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Status

- [x] Project structure & pyproject.toml
- [x] Multi-RPC client with rotation & failover
- [x] Core swap parser (balance-diff approach)
- [x] Token metadata resolver (Jupiter + cache)
- [x] Helius compatibility layer
- [x] Unit tests (73 tests, all passing)
- [x] Real transaction fixtures (7 mainnet transactions)
- [ ] CI (GitHub Actions)
- [ ] Publish to PyPI

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical design details.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_parser.py -v
pytest tests/test_rpc.py -v
pytest tests/test_integration.py -v
```

### Test Categories

| File | What it tests |
|------|---------------|
| `test_parser.py` | BUY/SELL detection, USDC pairs, ATA create/close, WSOL, edge cases |
| `test_rpc.py` | Round-robin, failover, batch, rate limiting, backoff |
| `test_metadata.py` | Cache load/save, preload, lazy resolve |
| `test_integration.py` | Real mainnet transactions end-to-end |
| `test_compat.py` | Helius format conversion |

### Adding Test Fixtures

Fixtures are real mainnet transactions stored in `tests/fixtures/`. Each is a JSON file with:
```json
{
  "tx": { ... },     // raw getTransaction response
  "wallet": "..."    // wallet address to parse
}
```

## Dependencies

```
requests>=2.28       # HTTP client (only runtime dependency)
pytest>=7.0          # Testing (dev only)
```

## Code Style

- Python 3.10+
- Type hints on public API
- Functions over classes (SolanaParser is a thin wrapper)
- Docstrings on public API only
- Tests for every edge case
