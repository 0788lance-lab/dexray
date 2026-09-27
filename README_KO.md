# DexRay — 무료 Solana DEX Swap 파서

**Jupiter, Raydium, Pump.fun, Orca, Meteora의 매매 거래를 무료 표준 RPC로 파싱 — Helius Enhanced API 대체 도구.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)](#테스트)

[English](README.md) | [中文](README_CN.md) | [日本語](README_JA.md) | [한국어](README_KO.md)

---

DexRay는 **모든 Solana DEX 스왑**을 구조화된 데이터(BUY/SELL, 토큰, 금액)로 파싱하는 Python 라이브러리입니다. 무료 표준 RPC 호출만 사용하며, `preTokenBalances`와 `postTokenBalances`의 차이를 비교하여 작동합니다. Helius Enhanced API 불필요, 벤더 종속 없음.

**사용 사례:** 트레이딩 봇, 지갑 분석기, 포트폴리오 트래커, 카피 트레이딩, 스마트 머니 분석, 온체인 분석.

> **왜 Solana만?** EVM 체인에는 표준화된 Event Logs가 있어 무료 RPC로 쉽게 스왑을 파싱할 수 있습니다. Solana는 유료 API(Helius $49+/월) 또는 자체 파서가 필요한 유일한 주요 체인입니다. DexRay가 바로 그 파서입니다 — 무료이며 오픈소스.

## 왜 DexRay인가?

| | Helius Enhanced API | DexRay |
|---|---|---|
| 비용 | $49+/월 | **무료** (표준 RPC) |
| 속도 제한 | 10-50 req/s | **무제한** (멀티 RPC 로테이션) |
| 벤더 종속 | Helius만 | **모든 Solana RPC** |
| 설정 | API 키 필요 | **제로 설정** |
| 오픈소스 | 아니오 | **예** |

## 빠른 시작

### 설치

```bash
pip install git+https://github.com/0788lance-lab/dexray.git
```

### 2줄로 스왑 파싱

```python
from dexray import SolanaParser

parser = SolanaParser()  # 제로 설정 — 무료 Solana 퍼블릭 RPC 사용

# 실제 Jupiter 스왑 파싱 (복사-붙여넣기로 바로 테스트 가능)
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
print(swap)
# => Swap(direction='BUY', sol_amount=0.03, token_amount=12899.01, source='JUPITER', ...)
```

### 더 많은 예제

```python
# PumpSwap 매수 파싱
swap = parser.parse_swap_by_sig(
    "3GnMkq8ozGkn2eMRSF7fLykRkwHmtDWxA9U1PHBeKsTU73pjUstQdNWqEhcyYZkTkd7VM7GzJGpJze6vDQxoTQpH",
    wallet="Fdg75QBKQ7UMMM4hrthGXxYvRCT5qtRAd8hnaXNGqs2K",
)
# => Swap(direction='BUY', sol_amount=1.01, token_amount=194259.73, source='PUMPSWAP', ...)

# Raydium 매도 파싱
swap = parser.parse_swap_by_sig(
    "5s17quVEjwJHtqtMZTo7Q6PLNwJQb3gnUnAhEd1y3p5e3MoWM5Nt7ZbqsZzWgCbWZRaeJ4Yb941BSfUpCuUr6pUM",
    wallet="6M1RhUfjmojYcY6QXqsDb1geG6Tpz8bzH2C8DRzzY8be",
)
# => Swap(direction='SELL', sol_amount=3.26, token_amount=460016.10, source='RAYDIUM_CPMM', ...)

# 지갑의 최근 거래 일괄 파싱
trades = parser.parse_wallet("85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7", limit=50)
for t in trades:
    print(f"{t.direction} {t.symbol or t.mint[:8]} | {t.sol_amount:.4f} SOL")
```

## 작동 원리

```
원시 트랜잭션 (getTransaction RPC)
  → preTokenBalances와 postTokenBalances 비교
  → 토큰 흐름 방향 감지
  → SOL 감소 + 토큰 증가 = 매수 (BUY)
  → SOL 증가 + 토큰 감소 = 매도 (SELL)
```

사용된 DEX에 **관계없이** 작동합니다 — Jupiter, Raydium, Pump.fun, Orca, Meteora 등. 프로그램별 명령어가 아닌 잔액 변화를 읽기 때문입니다.

## 지원 DEX

| DEX | 감지 |
|-----|------|
| Jupiter V6 | ✅ |
| Raydium V4 / CPMM / CLMM | ✅ |
| Pump.fun AMM / PumpSwap | ✅ |
| Orca Whirlpool | ✅ |
| Meteora DLMM / DAMM V2 | ✅ |
| *기타 모든 DEX* | ✅ (UNKNOWN으로 감지) |

## 추천 RPC 프로바이더

### 가입 불필요

| 프로바이더 | URL |
|-----------|-----|
| Solana Public | `https://api.mainnet-beta.solana.com` |
| SolanaTracker | `https://rpc.solanatracker.io/public` |
| PublicNode | `https://solana-rpc.publicnode.com` |

### 무료 가입 (신용카드 불필요)

| 프로바이더 | 무료 할당량 |
|-----------|------------|
| **Alchemy** (추천) | 30M CU/월, 25 RPS |
| **Chainstack** | 3M 요청/월, 25 RPS |
| **Helius** | 1M 크레딧/월, 10 RPS |

### 추천 설정 (프로덕션)

```python
from dexray import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",     # Alchemy (메인)
    "https://solana-mainnet.core.chainstack.com/YOUR_KEY",   # Chainstack (백업)
    "https://api.mainnet-beta.solana.com",                    # 퍼블릭 (폴백)
])

parser = SolanaParser(rpc)
```

## CLI 도구

```bash
# 단일 트랜잭션 파싱
python -m dexray parse <서명> <지갑주소>

# 지갑의 최근 스왑 스캔
python -m dexray scan <지갑주소> --limit 50
```

## 테스트

```bash
git clone https://github.com/0788lance-lab/dexray.git
cd dexray
pip install -e ".[dev]"
pytest tests/ -v
```

## 기여하기

기여를 환영합니다! 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

[MIT](LICENSE)
