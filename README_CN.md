# DexRay — 免费 Solana DEX Swap 解析器

**解析 Jupiter、Raydium、Pump.fun、Orca、Meteora 的买卖交易 — 使用免费标准 RPC，可直接替代 Helius Enhanced API。**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)](#测试)

[English](README.md) | [中文](README_CN.md)

---

DexRay 是一个 Python 库，可将**任意 Solana DEX swap** 解析为结构化数据（BUY/SELL、代币、金额、盈亏），仅使用免费标准 RPC 调用。核心原理：比较 `preTokenBalances` 与 `postTokenBalances` 的差值 — 无需 Helius Enhanced API，无需付费订阅，无供应商锁定。

**适用场景：** 交易机器人、钱包分析器、投资组合追踪、跟单交易、聪明钱分析、链上数据分析。

> **为什么只做 Solana？** EVM 链有标准化的 Event Logs，任何免费 RPC 都能轻松解析 swap。Solana 是唯一需要付费 API（Helius $49+/月）或自建解析器的主流公链。DexRay 就是这个解析器 — 免费且开源。

## 为什么选 DexRay？

| | Helius Enhanced API | DexRay |
|---|---|---|
| 费用 | $49+/月 | **免费**（标准 RPC） |
| 速率限制 | 10-50 请求/秒 | **无限制**（多 RPC 轮换） |
| 供应商锁定 | 仅 Helius | **任意 Solana RPC** |
| 配置 | 需要 API key | **零配置** |
| 开源 | 否 | **是** |

## 快速开始

### 安装

```bash
pip install git+https://github.com/0788lance-lab/dexray.git
```

### 两行代码解析一笔 swap

```python
from dexray import SolanaParser

parser = SolanaParser()  # 零配置 — 自动使用免费 Solana 公共 RPC

# 解析一笔真实的 Jupiter swap（可直接复制粘贴运行验证）
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
print(swap)
# => Swap(direction='BUY', sol_amount=0.03, token_amount=12899.01, source='JUPITER', ...)
```

### 更多示例

```python
# 解析 PumpSwap 买入
swap = parser.parse_swap_by_sig(
    "3GnMkq8ozGkn2eMRSF7fLykRkwHmtDWxA9U1PHBeKsTU73pjUstQdNWqEhcyYZkTkd7VM7GzJGpJze6vDQxoTQpH",
    wallet="Fdg75QBKQ7UMMM4hrthGXxYvRCT5qtRAd8hnaXNGqs2K",
)
# => Swap(direction='BUY', sol_amount=1.01, token_amount=194259.73, source='PUMPSWAP', ...)

# 解析 Raydium 卖出
swap = parser.parse_swap_by_sig(
    "5s17quVEjwJHtqtMZTo7Q6PLNwJQb3gnUnAhEd1y3p5e3MoWM5Nt7ZbqsZzWgCbWZRaeJ4Yb941BSfUpCuUr6pUM",
    wallet="6M1RhUfjmojYcY6QXqsDb1geG6Tpz8bzH2C8DRzzY8be",
)
# => Swap(direction='SELL', sol_amount=3.26, token_amount=460016.10, source='RAYDIUM_CPMM', ...)

# 批量解析钱包的最近交易
trades = parser.parse_wallet("85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7", limit=50)
for t in trades:
    print(f"{t.direction} {t.symbol or t.mint[:8]} | {t.sol_amount:.4f} SOL")
```

## 工作原理

DexRay 不解析 DEX 特有的指令格式，而是直接读取交易的**最终结果**：

```
原始交易 (getTransaction RPC)
  → 对比 preTokenBalances 与 postTokenBalances
  → 检测代币流向
  → SOL 减少 + 代币增加 = 买入 (BUY)
  → SOL 增加 + 代币减少 = 卖出 (SELL)
```

这种方法**适用于所有 DEX** — Jupiter、Raydium、Pump.fun、Orca、Meteora 以及未来的任何 DEX — 因为我们读的是余额变化，而非特定程序的指令。

## 功能特性

- **零配置** — 开箱即用，内置免费 Solana 公共 RPC，无需 API key
- **多 RPC 轮换** — 可添加多个免费 RPC 提供商以提高吞吐量
- **通用 DEX 支持** — Jupiter、Raydium、Pump.fun、Orca、Meteora 以及任何未来 DEX
- **稳定币交易对** — 支持 USDC/USDT 作为计价货币
- **代币元数据** — 通过 Jupiter 代币列表解析 mint 地址为代币符号
- **批量处理** — 高效的批量交易解析，带速率控制
- **Helius 兼容** — 可选兼容层，便于从 Helius 迁移

## 支持的 DEX

| DEX | 程序 ID | 检测 |
|-----|---------|------|
| Jupiter V6 | `JUP6Lkb...` | ✅ |
| Raydium V4 | `675kPX9...` | ✅ |
| Raydium CPMM | `CPMMoo8...` | ✅ |
| Raydium CLMM | `CAMMCzo...` | ✅ |
| Pump.fun AMM | `6EF8rre...` | ✅ |
| PumpSwap | `pAMMBay...` | ✅ |
| Orca Whirlpool | `whirLbM...` | ✅ |
| Meteora DLMM | `LBUZKhR...` | ✅ |
| Meteora DAMM V2 | `cpamdpZ...` | ✅ |
| *其他任意 DEX* | *任意* | ✅（标记为 UNKNOWN） |

> Swap 检测对**所有 DEX** 均有效。上表仅影响 `source` 标签。

## 推荐 RPC 提供商

DexRay 支持**任意** Solana RPC。以下为经过实测的免费提供商（截至 2026 年 9 月）：

### 无需注册

| 提供商 | URL | 速率限制 |
|--------|-----|----------|
| Solana 公共节点 | `https://api.mainnet-beta.solana.com` | ~5 RPS |
| SolanaTracker | `https://rpc.solanatracker.io/public` | 未知 |
| PublicNode | `https://solana-rpc.publicnode.com` | 未知 |

### 免费注册（无需信用卡）

| 提供商 | 免费配额 | 注册 |
|--------|---------|------|
| **Alchemy**（推荐） | 30M CU/月，25 RPS | [alchemy.com](https://www.alchemy.com) |
| **Chainstack** | 3M 请求/月，25 RPS | [chainstack.com](https://chainstack.com) |
| **Helius** | 1M credits/月，10 RPS | [helius.dev](https://helius.dev) |

### 已知不可用

| 提供商 | 问题 |
|--------|------|
| dRPC | 免费计划**不支持 Solana**（仅限 EVM 链） |
| Ankr | 仅保留 16 小时交易历史 — 无法用于钱包分析 |

### 推荐配置（生产环境）

```python
from dexray import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",     # Alchemy（主力）
    "https://solana-mainnet.core.chainstack.com/YOUR_KEY",   # Chainstack（备用）
    "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",      # Helius（备用）
    "https://api.mainnet-beta.solana.com",                    # 公共节点（兜底）
])

parser = SolanaParser(rpc)
```

## 进阶用法

### 按提供商限速

```python
rpc = MultiRPC([
    {"url": "https://api.mainnet-beta.solana.com", "rps": 5},
    {"url": "https://solana-mainnet.g.alchemy.com/v2/KEY", "rps": 25},
])
```

### 代币符号解析

```python
from dexray import SolanaParser, TokenResolver

resolver = TokenResolver()  # 自动加载 Jupiter 代币列表
parser = SolanaParser(resolver=resolver)

swap = parser.parse_swap_by_sig(sig, wallet=addr)
print(swap.symbol)  # => "BONK"（而非原始 mint 地址）
```

### 底层解析（无需 RPC）

```python
from dexray import parse_swap

# 如果你已经有了 getTransaction 的原始返回数据：
swap = parse_swap(raw_tx, wallet="你的钱包地址")
```

### 从 Helius 迁移

```python
from dexray import to_helius_format, parse_swap

swap = parse_swap(raw_tx, wallet)
helius_like = to_helius_format(swap)
# => 与 Helius Enhanced Transaction 响应格式相同
```

详见 [迁移指南](docs/MIGRATION.md)。

## API 参考

### `SolanaParser(rpc=None, resolver=None)`

主入口。默认使用免费 Solana 公共 RPC。

| 方法 | 说明 |
|------|------|
| `parse_swap_by_sig(sig, wallet)` | 获取并解析单笔交易 |
| `parse_wallet(wallet, limit=300)` | 解析钱包的近期 swap 历史 |

### `parse_swap(tx, wallet) → Swap | None`

纯函数。将 `getTransaction` 的原始响应解析为 `Swap`。非 swap 交易返回 `None`。

### `Swap` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `direction` | `str` | `"BUY"` 或 `"SELL"` |
| `mint` | `str` | 代币 mint 地址 |
| `symbol` | `str` | 代币符号（使用 resolver 时填充） |
| `sol_amount` | `float` | 花费的 SOL（买入）或收到的 SOL（卖出） |
| `usdc_amount` | `float` | USDC/USDT 金额（稳定币交易对时） |
| `token_amount` | `float` | 收到的代币数量（买入）或卖出的数量（卖出） |
| `timestamp` | `int` | Unix 时间戳 |
| `signature` | `str` | 交易签名 |
| `source` | `str` | DEX 名称（如 `"JUPITER"`、`"RAYDIUM"`） |
| `program` | `str` | DEX 程序地址 |

### `MultiRPC(endpoints=None, max_retries=3, timeout=30.0)`

| 方法 | 说明 |
|------|------|
| `get_transaction(sig)` | 获取单笔交易 |
| `get_signatures(address, limit)` | 获取地址的近期签名列表 |
| `batch_get_transactions(sigs, batch_size=10)` | 批量获取交易 |

### `TokenResolver(preload=True, cache_file=None)`

| 方法 | 说明 |
|------|------|
| `resolve(mint)` | 获取 mint 地址对应的代币符号 |
| `batch_resolve(mints)` | 批量解析 |
| `add(mint, symbol)` | 手动添加映射 |

## 项目结构

```
dexray/
├── dexray/
│   ├── __init__.py          # 包导出
│   ├── core.py              # Swap 数据类
│   └── solana/
│       ├── __init__.py
│       ├── parser.py        # Swap 解析器（余额差值法）
│       ├── rpc.py           # 多 RPC 客户端（轮换 + 容错）
│       ├── metadata.py      # 代币符号解析器
│       └── compat.py        # Helius 兼容层
├── tests/
│   ├── test_parser.py       # 解析器单元测试
│   ├── test_rpc.py          # RPC 客户端测试
│   ├── test_metadata.py     # 元数据解析器测试
│   ├── test_integration.py  # 真实交易集成测试
│   ├── test_compat.py       # Helius 兼容测试
│   └── fixtures/            # 真实主网交易样本
├── docs/
│   ├── ARCHITECTURE.md      # 技术架构
│   ├── DEVELOPMENT.md       # 开发指南
│   └── MIGRATION.md         # Helius 迁移指南
├── pyproject.toml
├── LICENSE
└── README.md
```

## 测试

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e ".[dev]"
pytest tests/ -v
```

73 个测试，覆盖：Jupiter、Raydium、PumpSwap、USDC 交易对、失败交易、ATA 创建/关闭等场景。

## 贡献

欢迎贡献！详见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

1. Fork 本仓库
2. 创建功能分支
3. 为改动编写测试
4. 提交 PR

## 许可证

[MIT](LICENSE)
