# Contributing to DexRay

Thanks for your interest in contributing!

## Getting Started

1. Fork the repo on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/dexray.git
   cd dexray
   ```
3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
pytest tests/ -v
```

All tests must pass before submitting a PR. Tests in `tests/fixtures/` use
recorded mainnet transactions so no RPC calls are needed.

## Parser Fixes Need a Real Transaction

Every fix to swap parsing must ship with the mainnet transaction it got wrong,
saved as a regression fixture:

```bash
python scripts/add_fixture.py <signature> --name <short_label> \
    --note "what was wrong" [--wallet <trader>]
```

The script stores the raw transaction plus the current parse as the expected
result in `tests/fixtures/regression/`, and prints the trader's raw balance
changes. Check the expected values against them before committing.
`tests/test_regression.py` then checks every fixture three ways: the pinned
expected fields, an independent re-computation from integer balances, and
trader inference without a wallet. No synthetic-only fixes.

## Data Quality Check

`python -m dexray check` samples recent swaps for every DEX program, parses
them, and scores the parser against raw balance changes (see
[docs/QUALITY.md](docs/QUALITY.md)). Run it before releasing parser changes.

## Code Style

- Python 3.10+ (use modern type hints: `dict[str, int]`, `list[str] | None`)
- Keep functions short and focused
- Add docstrings to public functions
- No unnecessary comments

## Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```
2. Make your changes and add tests
3. Run `pytest tests/ -v` to verify
4. Push and open a PR against `main`
5. Describe what your PR does and why

## Reporting Issues

When filing a bug report, please include:

- Python version (`python --version`)
- DexRay version (`python -c "import dexray; print(dexray.__version__)"`)
- Minimal code to reproduce the issue
- Full error traceback

## Adding DEX Support

To add detection for a new DEX program:

1. Add the program ID to `DEX_PROGRAMS` in `dexray/solana/parser.py`
2. Add a regression fixture for a real swap on it (`scripts/add_fixture.py`)
3. The balance-diff approach should work automatically for any DEX

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
