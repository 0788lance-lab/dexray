"""Shared types for DexRay Solana swap parsing."""

from dataclasses import dataclass


@dataclass
class Swap:
    """Parsed swap result."""
    direction: str          # "BUY" or "SELL"
    mint: str               # token mint address
    symbol: str             # human-readable symbol (e.g., "BONK")
    sol_amount: float       # SOL spent (BUY) or received (SELL)
    usdc_amount: float      # USDC spent/received (if stablecoin pair)
    token_amount: float     # token amount received (BUY) or sent (SELL)
    timestamp: int          # unix timestamp
    signature: str          # transaction signature
    source: str             # DEX name (e.g., "JUPITER", "RAYDIUM")
    program: str            # on-chain program address

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "mint": self.mint,
            "symbol": self.symbol,
            "sol_amount": self.sol_amount,
            "usdc_amount": self.usdc_amount,
            "token_amount": self.token_amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "source": self.source,
            "program": self.program,
        }
