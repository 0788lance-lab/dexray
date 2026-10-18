"""Shared types for DexRay Solana swap parsing."""

from dataclasses import dataclass


@dataclass
class Swap:
    """Parsed swap result."""
    direction: str          # "BUY" or "SELL"
    mint: str               # token mint address
    symbol: str             # human-readable symbol (e.g., "BONK")
    sol_amount: float       # SOL spent (BUY) or received (SELL); 0 when quote is not SOL
    usdc_amount: float      # stablecoin (USDC/USDT) spent/received; prefer quote_amount
    token_amount: float     # token amount received (BUY) or sent (SELL)
    timestamp: int          # unix timestamp
    signature: str          # transaction signature
    source: str             # DEX name (e.g., "JUPITER", "RAYDIUM")
    program: str            # on-chain program address
    quote_mint: str = ""    # mint paid (BUY) or received (SELL); WSOL mint for native SOL
    quote_amount: float = 0.0  # quote_mint amount in human units
    trader: str = ""        # wallet whose balances were parsed
    fee_payer: str = ""     # accountKeys[0]; differs from trader for relayer-paid txs

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
            "quote_mint": self.quote_mint,
            "quote_amount": self.quote_amount,
            "trader": self.trader,
            "fee_payer": self.fee_payer,
        }
