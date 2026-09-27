"""Minimal example: parse a real Jupiter swap."""

from dexray import SolanaParser

parser = SolanaParser()
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
if swap:
    print(f"{swap.direction} | {swap.sol_amount:.4f} SOL | {swap.token_amount:.2f} tokens | {swap.source}")
else:
    print("Swap not found or not parseable.")
