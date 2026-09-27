# DexRay Development Guide

## Development Phases

### Phase 0: Project Setup (Day 1 Morning)

- [x] Project structure & documentation
- [ ] `pyproject.toml` / `setup.py` with dependencies
- [ ] Git init & `.gitignore`
- [ ] Collect real transaction fixtures for testing

### Phase 1: Core Parser (Day 1)

**Goal**: Parse raw Solana transactions into structured swap data.

#### 1.1 Transaction Fixtures
Collect 20+ real transactions covering all edge cases:
```bash
# Fetch sample transactions from different DEXes
python examples/collect_fixtures.py
```

Categories needed:
- Jupiter swap (SOL → token)
- Jupiter swap (token → SOL)
- Raydium v4 swap
- Pump.fun AMM buy/sell
- PumpSwap buy/sell
- USDC pair swap
- Multi-hop swap
- Failed transaction
- Non-swap transaction (transfer, etc.)
- Wrap/unwrap SOL

#### 1.2 Core Parser Implementation (`dexray/solana/parser.py`)

Key function signature:
```python
def parse_swap(
    tx: dict,              # raw getTransaction response
    wallet: str,           # wallet address to track
    quote_mints: set = QUOTE_MINTS,  # SOL, USDC, USDT
) -> dict | None:
    """
    Parse a single transaction into swap data.
    Returns None if not a detectable swap.
    """
```

Implementation steps:
1. Check `meta.err` — skip failed transactions
2. Find wallet's index in `accountKeys`
3. Compute SOL delta from `preBalances` / `postBalances`
4. Build token delta map from `preTokenBalances` / `postTokenBalances`
5. Match: SOL change ↔ token change → BUY or SELL
6. Handle USDC/USDT as alternative quote currency
7. Extract program ID from instructions for DEX identification

#### 1.3 Batch Parser (`parse_wallet`)
```python
def parse_wallet(
    rpc: MultiRPC,
    wallet: str,
    limit: int = 300,
) -> list[dict]:
    """Fetch and parse a wallet's recent swap history."""
```

#### 1.4 Testing
```bash
pytest tests/test_parser.py -v
```

Each fixture transaction should have expected output defined. Compare DexRay output vs known Helius Enhanced output.

### Phase 2: Multi-RPC Client (Day 1)

**Goal**: Distribute load across multiple free RPC providers.

#### 2.1 Provider Configuration
```python
# Default free providers (user adds their own keys)
DEFAULT_PROVIDERS = [
    {"url": "https://api.mainnet-beta.solana.com", "rps": 5, "name": "solana-public"},
]

# User configures additional providers
rpc = MultiRPC([
    "https://lb.drpc.org/ogrpc?network=solana&dkey=YOUR_KEY",       # dRPC: 50M CU/mo free
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",             # Alchemy: 300M req free
    "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",             # Helius: existing free key
])
```

#### 2.2 Rotation & Retry Logic
```
Request → Provider A → 429? → Provider B → 429? → Provider C → backoff → retry
```

- Track per-provider error rate
- Deprioritize providers with recent 429s
- Configurable rate limit per provider
- Automatic health recovery after cooldown

#### 2.3 Batch RPC
Solana supports JSON-RPC batching (multiple calls in one HTTP request):
```python
# Instead of 10 separate HTTP calls:
results = rpc.batch_get_transactions(signatures[:10])
```

### Phase 3: Token Metadata (Day 2 Morning)

**Goal**: Resolve mint addresses to human-readable symbols.

#### 3.1 Resolution Chain
1. Local cache (memory + `~/.dexray/token_cache.json`)
2. Jupiter Token List API (`https://token.jup.ag/all`)
3. On-chain Metaplex metadata (fallback)

#### 3.2 Cache Strategy
- Pre-load top 1000 tokens from Jupiter on startup
- Cache indefinitely (token symbols don't change)
- Lazy-load unknown mints on first encounter

### Phase 4: Integration with MemeRadar (Day 2)

**Goal**: Replace Helius Enhanced API calls in memeradar with DexRay.

#### 4.1 wallet_analyzer.py Migration
```python
# Before (Helius Enhanced API):
r = requests.post(ENHANCED_URL, json=signatures)
txs = r.json()
swaps = parse_helius_txs(txs, wallet)

# After (DexRay):
from dexray.solana import SolanaParser, MultiRPC
rpc = MultiRPC([...])
parser = SolanaParser(rpc)
swaps = parser.parse_wallet(wallet, limit=300)
```

#### 4.2 paper_trader.py Migration
```python
# Before:
r = requests.post(ENHANCED_URL, json=[sig])
txs = r.json()
parsed = parse_helius_txs(txs, wallet)

# After:
tx = rpc.get_transaction(sig)
swap = parser.parse_swap(tx, wallet)
```

#### 4.3 Validation
Run both parsers (Helius + DexRay) in parallel for 24h, compare outputs, fix discrepancies.

### Phase 5: Polish & Open Source (Day 2 Afternoon)

- [ ] Clean up API surface
- [ ] Write examples
- [ ] Add CI (GitHub Actions)
- [ ] Publish to PyPI
- [ ] Write migration guide

## Testing Strategy

### Unit Tests
```python
# tests/test_parser.py
def test_jupiter_buy():
    """Jupiter SOL→token swap correctly identified as BUY."""
    tx = load_fixture("jupiter_buy.json")
    result = parse_swap(tx, WALLET)
    assert result["direction"] == "BUY"
    assert result["sol_amount"] > 0
    assert result["token_amount"] > 0

def test_failed_tx_skipped():
    """Failed transactions return None."""
    tx = load_fixture("failed_tx.json")
    assert parse_swap(tx, WALLET) is None
```

### Integration Tests
```python
# tests/test_integration.py
def test_vs_helius():
    """Compare DexRay output against Helius Enhanced API for same transactions."""
    for sig in SAMPLE_SIGNATURES:
        helius_result = fetch_helius_enhanced(sig)
        dexray_result = parser.parse_swap(rpc.get_transaction(sig), wallet)
        assert dexray_result["direction"] == helius_result["direction"]
        assert abs(dexray_result["sol_amount"] - helius_result["sol_amount"]) < 0.0001
```

## Dependencies

```
requests>=2.28       # HTTP client
websockets>=11.0     # WebSocket for live monitoring (optional)
```

No heavy dependencies. No web frameworks. No ORMs. Pure Python + requests.

## Code Style

- Python 3.10+
- Type hints everywhere
- No classes where functions suffice
- Docstrings for public API only
- Tests for every edge case
