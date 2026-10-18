# Data Quality Check

DEX programs get upgraded, new transaction versions ship, relayers change how
fees are paid. Any of these can make the parser silently wrong: it keeps
running, raises nothing, and returns bad numbers. Unit tests only prove the
code was right when it was written. The quality check is the live alarm.

```bash
python -m dexray check                       # all DEXes, 50 swaps each, public RPC
python -m dexray check --dex ORCA --per-dex 20
python -m dexray check --rpc https://your-rpc --rps 10 --out quality_reports
```

Exit code `2` means an alert fired. Reports (`quality-<timestamp>.json` + `.md`)
accumulate in `--out`; each Markdown report has a per-DEX trend table across the
last 8 runs.

## How it works

For each DEX program:

1. Take the program's last 1000 successful signatures (fixed shuffle so one
   bot's burst doesn't dominate).
2. Fetch txs until 50 swaps are scored or 200 txs fetched. Most program
   traffic is arbitrage bots and liquidity management, not user swaps.
3. Parse each tx **without a wallet** (trader inferred), and judge it with an
   independent oracle (`dexray/solana/quality.py`) that works only from
   integer pre/post balances:
   - *is it a swap?* some signer has exactly one asset in and one out
     (SOL + WSOL merged, fee added back for the fee payer, SOL under 0.01 and
     routing dust under 1e-6 ignored);
   - *is the parse right?* direction matches the signs, `token_amount` and
     `quote_amount` equal the raw deltas, the trader signed the tx and is the
     swapping signer, `fee_payer` is `accountKeys[0]`.

Every scored swap is checked (a superset of the 5-amount / 5-direction spot
check), and 5 verified sigs per DEX are listed with Solscan links for a human
look.

| Outcome | Meaning | Counts against rate |
|---|---|---|
| ok | parsed and verified | — |
| missed | oracle says swap, parser returned `None` | yes |
| wrong | parsed, but amounts/direction/trader disagree with raw balances | yes |
| rpc err | RPC refused the tx (e.g. `-32015` unsupported version) | yes |
| exc | `parse_swap` raised | yes |
| spurious | parsed a tx the oracle doesn't consider a swap (SOL leg under 0.01 excluded) | no, listed for review |
| unavailable | 429 / timeout / not found | no, reported |

**Alerts** (exit 2, Telegram/Slack if configured): a DEX below the threshold
(default 98%); any `wrong` parse or exception even above the threshold (1 wrong
in 50 is exactly 98%, and silent miscalculation is the failure this exists to
catch); or a program with no recent transactions at all (wrong or migrated
program ID). **Warnings** (report only): fewer than 10 scored swaps.

## Notifications

| Env var | Effect |
|---|---|
| `DEXRAY_TELEGRAM_BOT_TOKEN` + `DEXRAY_TELEGRAM_CHAT_ID` | Telegram message on alert |
| `DEXRAY_SLACK_WEBHOOK` | Slack incoming-webhook message on alert |

## Schedule

`.github/workflows/quality.yml` runs every Monday 03:00 UTC (and on demand).
A failing run is the alert; the report is in the run summary and as an
artifact, and past reports are restored from the Actions cache for the trend.
No secrets are required: without `SOLANA_RPC_URL` it uses the public RPC
(~30 min per run), and a failed run already notifies the repo owner through
GitHub's standard workflow emails. Scheduled workflows don't run on forks
until enabled there; if you run your own, optionally add `SOLANA_RPC_URL` and
the notification variables above as secrets in your repo.

Local cron alternative:

```cron
0 3 * * 1  cd /path/to/dexray && python -m dexray check --out quality_reports >> quality.log 2>&1
```

## When it alerts

1. Open the report's *Problems* section; each line has the signature.
2. Reproduce: `python -m dexray parse <sig> <trader>`.
3. Fix the parser, then add the tx as a regression fixture
   (`scripts/add_fixture.py`, see CONTRIBUTING) so it can't come back.

## Baseline (2026-10-17)

Public RPC, 50-swap target per DEX, trader inferred (no wallet):

| DEX | txs fetched | swaps scored | ok | rate |
|---|---|---|---|---|
| JUPITER | 97 | 50 | 50 | 100% |
| RAYDIUM | 99 | 50 | 50 | 100% |
| RAYDIUM_CPMM | 110 | 50 | 50 | 100% |
| RAYDIUM_CLMM | 200 | 10 | 10 | 100% |
| PUMP_AMM | 200 | 43 | 43 | 100% |
| PUMPSWAP | 196 | 50 | 50 | 100% |
| ORCA | 167 | 50 | 50 | 100% |
| METEORA_DLMM | 200 | 22 | 22 | 100% |
| METEORA_DAMM_V2 | 114 | 50 | 50 | 100% |

Earlier runs the same day found real problems, all fixed with regression
fixtures: the Raydium CLMM program ID did not exist on chain (0 signatures),
a CLMM close-position was parsed as a swap, and the oracle itself needed to
ignore routing dust and accept bundles with two traders.

### Self-test: the check must fire on a broken build

Same 3 DEXes (Jupiter, PumpSwap, Pump AMM), 30-swap target, PublicNode RPC:

| Build | Result |
|---|---|
| current | 100% / 100% / 100%, no alert |
| old `rpc.py` (`maxSupportedTransactionVersion: 0`) | 43% / 30% / 23%, alert on all three (`-32015` rpc errors) |
| fee always added back (the pre-fix P0-2 bug, one line) | PumpSwap alert: `quote_amount 8.546437746 != chain 8.546427746` on a relayer-paid swap |

Unit tests (`tests/test_quality.py`) repeat this offline against the
regression fixtures: flipped direction, dropped decimals, a parser that
raises, a parser that returns nothing, RPC refusing v1 txs, and a single
wrong amount above the threshold all alert.
