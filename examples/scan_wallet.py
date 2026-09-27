"""Scan a wallet's recent swap transactions."""

import sys
from dexray import SolanaParser

wallet = sys.argv[1] if len(sys.argv) > 1 else "85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7"
parser = SolanaParser()
trades = parser.parse_wallet(wallet, limit=20)
print(f"Found {len(trades)} swaps for {wallet[:12]}...\n")
for t in trades:
    print(f"  {t.direction:4s} | {t.sol_amount:10.4f} SOL | {t.token_amount:>15.2f} tokens | {t.source}")
