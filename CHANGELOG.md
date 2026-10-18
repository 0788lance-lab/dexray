# Changelog

## [0.2.0] - 2026-10-18

Cleaner data on real mainnet traffic, plus a live check that it stays that way.

### Added
- `Swap.quote_mint` / `Swap.quote_amount`: the asset and amount on the other side of every swap (SOL, USDC, USDT, or the sent token in token-to-token swaps). `sol_amount` / `usdc_amount` are kept for compatibility.
- `Swap.trader` / `Swap.fee_payer`: relayer-paid ("gasless") swaps report the signing wallet as trader and the relayer as fee payer.
- `parse_swap(tx)` without a wallet infers the trader.
- `parse_swap(..., quote_mints=...)` sets quote priority.
- Token-to-token and SOL-to-stablecoin swaps are parsed (previously `None`).
- `python -m dexray check`: live data-quality check per DEX against raw balance changes, with weekly report, trend and Telegram/Slack alerts; weekly GitHub Actions workflow.
- Regression suite of real mainnet transactions (`tests/test_regression.py`) and `scripts/add_fixture.py`.
- Helius compat: non-SOL quote leg in `tokenTransfers` / swap event, `feePayer`.

### Changed
- `parse_swap(tx, wallet)`: `wallet` is now optional.
- `quote_mints` is an ordered priority list (it was accepted but unused before).
- WSOL token balances count toward the SOL leg instead of being ignored.
- Two assets moving the same way on the quote side (liquidity add/remove) returns `None` instead of a swap.
- DEX labels for multi-hop routes may differ from 0.1.0 (see Fixed).
- `MultiRPC` requests `maxSupportedTransactionVersion: 1`.

### Fixed
- Version 1 transactions: RPC requests now send `maxSupportedTransactionVersion: 1`; with `0` the RPC refused them (-32015).
- Relayer-paid swaps: the network fee was added back to the trader's SOL change even though the relayer paid it (e.g. 0.407988466 instead of 0.408 SOL).
- Amounts are computed from raw integer balances; `uiAmount` float subtraction gave values like 31.584113999999985.
- USDT-quoted swaps are no longer indistinguishable from USDC (`quote_mint`).
- Swaps settling into a persistent WSOL account were missed (WSOL was ignored); WSOL now counts toward the SOL leg.
- Several token accounts of the same mint are summed instead of the last one winning.
- Helius compat `nativeInput`/`nativeOutput` lamports were truncated (0.408 SOL → 407999999).
- Raydium CLMM program ID was wrong (`CAMMCzo5...Qi6Mc` does not exist on chain); now `CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK`. CLMM swaps were never labeled `RAYDIUM_CLMM` before.
- Liquidity operations (e.g. Raydium CLMM close position: NFT burned, USDC + token returned) were parsed as swaps; two assets moving the same way on the quote side now means "not a swap".
- DEX label for multi-hop routes: only the outermost DEX calls count (an aggregator such as Jupiter wrapping its legs stays `JUPITER`), and among sibling calls the one that delivers the token wins. E.g. a router doing USDC → SOL on Jupiter then SOL → token on PumpSwap is `PUMPSWAP`, not the first DEX instruction.

## [0.1.0] - 2026-09-27

### Added
- Core swap parser with balance-diff approach
- Multi-RPC client with round-robin rotation and failover
- Token metadata resolver (Jupiter token list + cache)
- Helius Enhanced API compatibility layer
- Support for 9 DEX programs (Jupiter, Raydium, Pump.fun, Orca, Meteora)
- CLI tool (`python -m dexray`)
- 73 unit and integration tests
- Multilingual documentation (English, 中文, 日本語, 한국어)

[0.2.0]: https://github.com/0788lance-lab/dexray/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/0788lance-lab/dexray/releases/tag/v0.1.0
