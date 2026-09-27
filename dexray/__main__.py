"""CLI entry point: python -m dexray"""

import argparse
import sys

from dexray import SolanaParser


def _short_sig(sig: str) -> str:
    return sig[:8] + "..." if len(sig) > 8 else sig


def cmd_parse(args):
    parser = SolanaParser()
    try:
        swap = parser.parse_swap_by_sig(args.signature, wallet=args.wallet)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if swap is None:
        print("Not a swap (or transaction not found).")
        sys.exit(0)

    label = swap.symbol or swap.mint[:12] + "..."
    print(f"{swap.direction:4s} | {swap.sol_amount:.4f} SOL | {swap.token_amount:.2f} tokens | {swap.source} | {label}")
    print(f"  sig: {_short_sig(swap.signature)}")
    print(f"  mint: {swap.mint}")


def cmd_scan(args):
    parser = SolanaParser()
    try:
        trades = parser.parse_wallet(args.wallet, limit=args.limit)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(trades)} swaps for {args.wallet[:12]}...\n")
    for t in trades:
        print(f"  {t.direction:4s} | {t.sol_amount:10.4f} SOL | {t.token_amount:>15.2f} tokens | {t.source:16s} | sig:{_short_sig(t.signature)}")


def main():
    ap = argparse.ArgumentParser(prog="dexray", description="DexRay — Solana DEX swap parser")
    sub = ap.add_subparsers(dest="command")

    p_parse = sub.add_parser("parse", help="Parse a single swap transaction")
    p_parse.add_argument("signature", help="Transaction signature")
    p_parse.add_argument("wallet", help="Wallet address")

    p_scan = sub.add_parser("scan", help="Scan a wallet's recent swaps")
    p_scan.add_argument("wallet", help="Wallet address")
    p_scan.add_argument("--limit", type=int, default=50, help="Max signatures to fetch (default: 50)")

    args = ap.parse_args()
    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "scan":
        cmd_scan(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
