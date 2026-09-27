"""Shared types and interfaces across chains."""

from dataclasses import dataclass


@dataclass
class Swap:
    """Parsed swap result — chain-agnostic."""
    direction: str          # "BUY" or "SELL"
    mint: str               # token mint/contract address
    symbol: str             # human-readable symbol (e.g., "BONK")
    base_amount: float      # quote currency amount (SOL, ETH, USDC, etc.)
    base_currency: str      # "SOL", "ETH", "USDC", etc.
    token_amount: float     # token amount received (BUY) or sent (SELL)
    timestamp: int          # unix timestamp
    signature: str          # transaction hash/signature
    source: str             # DEX name (e.g., "JUPITER", "UNISWAP")
    program: str            # on-chain program/contract address

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "mint": self.mint,
            "symbol": self.symbol,
            "base_amount": self.base_amount,
            "base_currency": self.base_currency,
            "token_amount": self.token_amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "source": self.source,
            "program": self.program,
        }
