"""Use multiple RPC providers for higher throughput."""

from dexray import SolanaParser, MultiRPC

rpc = MultiRPC([
    "https://api.mainnet-beta.solana.com",
    # Add more free RPCs:
    # "https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY",
    # "https://solana-mainnet.core.chainstack.com/YOUR_KEY",
])
parser = SolanaParser(rpc)
swap = parser.parse_swap_by_sig(
    "29SX7Qi7UCjrDNeBiYG3r7dWMVnMoPkPX5yENdSewtLr3mkX3LKpUGNFsvUxJo2mtV3zjTTSuHWPCn6dZcmEqvJe",
    wallet="85Z8rgvTwaWVfHb7kHBBuq8uuJdvB72vhXW8oJjP3zC7",
)
if swap:
    print(f"{swap.direction} | {swap.sol_amount:.4f} SOL | {swap.source}")
    print(f"Mint: {swap.mint}")
else:
    print("Swap not found or not parseable.")
