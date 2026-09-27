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
2. Add a test case in `tests/test_parser.py` with a real transaction fixture
3. The balance-diff approach should work automatically for any DEX

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
