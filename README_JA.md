# DexRay — 無料 Solana DEX Swap パーサー

**Jupiter、Raydium、Pump.fun、Orca、Meteoraの売買取引を無料の標準RPCで解析 — Helius Enhanced APIの代替ツール。**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)](#テスト)

[English](README.md) | [中文](README_CN.md) | [日本語](README_JA.md) | [한국어](README_KO.md)

---

DexRayは**あらゆるSolana DEXスワップ**を構造化データ（BUY/SELL、トークン、金額）に変換するPythonライブラリです。無料の標準RPCコールのみを使用し、`preTokenBalances`と`postTokenBalances`の差分を比較して動作します。Helius Enhanced API不要、ベンダーロックイン無し。

**ユースケース：** トレーディングボット、ウォレット分析、ポートフォリオトラッカー、コピートレード、スマートマネー分析、オンチェーン分析。

> **なぜSolanaだけ？** EVMチェーンには標準化されたEvent Logsがあり、無料RPCで簡単にスワップを解析できます。Solanaは有料API（Helius $49+/月）か独自パーサーが必要な唯一の主要チェーンです。DexRayがそのパーサーです — 無料でオープンソース。

## なぜDexRay？

| | Helius Enhanced API | DexRay |
|---|---|---|
| コスト | $49+/月 | **無料**（標準RPC） |
| レート制限 | 10-50 req/s | **無制限**（マルチRPCローテーション） |
| ベンダーロックイン | Heliusのみ | **任意のSolana RPC** |
| セットアップ | APIキー必要 | **ゼロコンフィグ** |
| オープンソース | いいえ | **はい** |

## クイックスタート

### インストール

```bash
pip install git+https://github.com/0788lance-lab/dexray.git
```

### 2行でスワップを解析

```python
from dexray import SolanaParser

parser = SolanaParser()  # ゼロコンフィグ — 無料のSolana公開RPCを使用

# 実際のJupiterスワップを解析（コピペで動作確認可能）
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
print(swap)
# => Swap(direction='BUY', sol_amount=0.03, token_amount=12899.01, source='JUPITER', ...)
```

### その他の例

```python
# PumpSwapの購入を解析
swap = parser.parse_swap_by_sig(
    "3GnMkq8ozGkn2eMRSF7fLykRkwHmtDWxA9U1PHBeKsTU73pjUstQdNWqEhcyYZkTkd7VM7GzJGpJze6vDQxoTQpH",
    wallet="Fdg75QBKQ7UMMM4hrthGXxYvRCT5qtRAd8hnaXNGqs2K",
)
# => Swap(direction='BUY', sol_amount=1.01, token_amount=194259.73, source='PUMPSWAP', ...)

# Raydiumの売却を解析
swap = parser.parse_swap_by_sig(
    "5s17quVEjwJHtqtMZTo7Q6PLNwJQb3gnUnAhEd1y3p5e3MoWM5Nt7ZbqsZzWgCbWZRaeJ4Yb941BSfUpCuUr6pUM",
    wallet="6M1RhUfjmojYcY6QXqsDb1geG6Tpz8bzH2C8DRzzY8be",
)
# => Swap(direction='SELL', sol_amount=3.26, token_amount=460016.10, source='RAYDIUM_CPMM', ...)

# ウォレットの最近の取引をバッチ解析
trades = parser.parse_wallet("85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7", limit=50)
for t in trades:
    print(f"{t.direction} {t.symbol or t.mint[:8]} | {t.sol_amount:.4f} SOL")
```

## 仕組み

```
生のトランザクション (getTransaction RPC)
  → preTokenBalances と postTokenBalances を比較
  → トークンフローの方向を検出
  → SOL減少 + トークン増加 = 購入 (BUY)
  → SOL増加 + トークン減少 = 売却 (SELL)
```

使用されたDEXに**関係なく**動作します — Jupiter、Raydium、Pump.fun、Orca、Meteoraなど。プログラム固有の命令ではなく、残高の変化を読み取るためです。

## 対応DEX

| DEX | 検出 |
|-----|------|
| Jupiter V6 | ✅ |
| Raydium V4 / CPMM / CLMM | ✅ |
| Pump.fun AMM / PumpSwap | ✅ |
| Orca Whirlpool | ✅ |
| Meteora DLMM / DAMM V2 | ✅ |
| *その他すべてのDEX* | ✅（UNKNOWNとして検出） |

## 推奨RPCプロバイダー

### 登録不要

| プロバイダー | URL |
|-------------|-----|
| Solana Public | `https://api.mainnet-beta.solana.com` |
| SolanaTracker | `https://rpc.solanatracker.io/public` |
| PublicNode | `https://solana-rpc.publicnode.com` |

### 無料登録（クレジットカード不要）

| プロバイダー | 無料枠 |
|-------------|--------|
| **Alchemy**（推奨） | 30M CU/月、25 RPS |
| **Chainstack** | 3M リクエスト/月、25 RPS |
| **Helius** | 1M クレジット/月、10 RPS |

### 推奨設定（本番環境）

```python
from dexray import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",     # Alchemy（メイン）
    "https://solana-mainnet.core.chainstack.com/YOUR_KEY",   # Chainstack（バックアップ）
    "https://api.mainnet-beta.solana.com",                    # パブリック（フォールバック）
])

parser = SolanaParser(rpc)
```

## CLIツール

```bash
# 単一トランザクションを解析
python -m dexray parse <署名> <ウォレットアドレス>

# ウォレットの最近のスワップをスキャン
python -m dexray scan <ウォレットアドレス> --limit 50
```

## テスト

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e ".[dev]"
pytest tests/ -v
```

## コントリビュート

コントリビュート歓迎！詳細は [CONTRIBUTING.md](CONTRIBUTING.md) をご覧ください。

## ライセンス

[MIT](LICENSE)
