# DexRay RPC Provider 调研报告（2026-09-27 实测）

## 给 DexRay README 的更新内容

以下是经过实际注册、测试、验证后的 Solana RPC 提供商真实情况。请更新 README 的 Quick Start 和相关章节。

---

## 实测可用的免费 Solana RPC

### 无需注册（直接可用）

| 提供商 | URL | 速率限制 | 适用场景 | 备注 |
|---|---|---|---|---|
| **Solana Public** | `https://api.mainnet-beta.solana.com` | ~5 RPS | 备用 | 官方公共节点，高峰期慢 |
| **SolanaTracker** | `https://rpc.solanatracker.io/public` | 未知 | 备用 | 无需注册，支持 sendTransaction |
| **PublicNode** | `https://solana-rpc.publicnode.com` | 未知 | 备用 | 无需注册 |

### 需注册（免费，无需信用卡）

| 提供商 | 免费配额 | 注册地址 | URL 格式 | 实测结果 |
|---|---|---|---|---|
| **Alchemy** | 30M CU/月，25 RPS | https://www.alchemy.com | `https://solana-mainnet.g.alchemy.com/v2/<KEY>` | **推荐主力**，配额最大，稳定 |
| **Chainstack** | 3M 请求/月，25 RPS | https://chainstack.com | `https://solana-mainnet.core.chainstack.com/<KEY>` | **推荐备用**，支持 GitHub 登录 |
| **Helius** | 1M credits/月，10 RPS | https://helius.dev | `https://mainnet.helius-rpc.com/?api-key=<KEY>` | 标准 RPC 可用，Enhanced API 不在 DexRay 范围 |
| **QuickNode** | 10M credits/月 | https://quicknode.com | 控制台生成 | 未实测，可能是 7 天试用期而非永久免费 |

### 确认不可用

| 提供商 | 原因 | 详情 |
|---|---|---|
| **dRPC** | 免费计划不支持 Solana | 返回 "chain is not available on free plan"，210M CU 只能用于 EVM 链 |
| **Ankr** | 只保留 16 小时交易历史 | `getTransaction` 查询超过 16 小时的交易返回 null，无法用于钱包历史分析 |

---

## 推荐配置

### 最小配置（开发/测试）
```python
from dexray.solana import MultiRPC

rpc = MultiRPC([
    "https://api.mainnet-beta.solana.com",  # 无需注册
])
```

### 推荐配置（生产）
```python
rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",          # Alchemy 30M CU/月（主力）
    "https://solana-mainnet.core.chainstack.com/YOUR_KEY",       # Chainstack 3M 请求/月
    "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",          # Helius 1M credits/月
    "https://api.mainnet-beta.solana.com",                       # Solana 公共（兜底）
    "https://rpc.solanatracker.io/public",                       # SolanaTracker（兜底）
    "https://solana-rpc.publicnode.com",                         # PublicNode（兜底）
])
```

### 性能实测（6 家轮换）

| 指标 | 结果 |
|---|---|
| 单钱包扫描（sig_limit=100） | **9 秒** |
| 429 错误 | **0 次** |
| 批量扫描 2000 钱包预估 | **~5 小时** |
| Helius Enhanced API 调用 | **0 次** |

---

## README 建议更新的章节

### 1. Quick Start 示例代码更新
把 dRPC 从示例中去掉，换成 Alchemy + Chainstack：

```python
from dexray.solana import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY",  # 免费 30M CU/月
    "https://solana-mainnet.core.chainstack.com/YOUR_CHAINSTACK_KEY",  # 免费 3M 请求/月
    "https://api.mainnet-beta.solana.com",  # 公共兜底
])

parser = SolanaParser(rpc)
trades = parser.parse_wallet("YourWalletAddress...", limit=100)
```

### 2. 新增 "Recommended RPC Providers" 章节
内容就是上面的实测表格。重点说明：
- Alchemy 是主力（配额最大）
- dRPC 免费计划**不支持 Solana**，不要推荐
- Ankr 只有 16 小时历史，**不适合钱包分析**
- 公共 RPC 做兜底，不能单独依赖

### 3. MIGRATION.md 更新
MultiRPC 示例中去掉 dRPC，加 Chainstack。
