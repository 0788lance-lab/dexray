"""CLI entry point: python -m dexray"""

import argparse
import logging
import sys

from dexray import SolanaParser, MultiRPC
from dexray.solana.parser import DEX_PROGRAMS, WSOL, USDC, USDT

_QUOTE_SYMBOLS = {WSOL: "SOL", USDC: "USDC", USDT: "USDT"}


def _short_sig(sig: str) -> str:
    return sig[:8] + "..." if len(sig) > 8 else sig


def _quote(swap) -> str:
    symbol = _QUOTE_SYMBOLS.get(swap.quote_mint, swap.quote_mint[:6])
    return f"{swap.quote_amount:.4f} {symbol}"


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
    print(f"{swap.direction:4s} | {_quote(swap)} | {swap.token_amount:.2f} tokens | {swap.source} | {label}")
    print(f"  sig: {_short_sig(swap.signature)}")
    print(f"  mint: {swap.mint}")
    if swap.fee_payer != swap.trader:
        print(f"  fee payer: {swap.fee_payer} (relayer)")


def cmd_scan(args):
    parser = SolanaParser()
    try:
        trades = parser.parse_wallet(args.wallet, limit=args.limit)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(trades)} swaps for {args.wallet[:12]}...\n")
    for t in trades:
        print(f"  {t.direction:4s} | {_quote(t):>20s} | {t.token_amount:>15.2f} tokens | {t.source:16s} | sig:{_short_sig(t.signature)}")


def cmd_check(args):
    from dexray.solana.quality import run_check, save_report, notify

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    rpc = MultiRPC([{"url": u, "rps": args.rps} for u in args.rpc] if args.rpc else None)
    programs = DEX_PROGRAMS
    if args.dex:
        wanted = {d.upper() for d in args.dex}
        programs = {p: s for p, s in DEX_PROGRAMS.items() if s in wanted}
    report = run_check(rpc, per_dex=args.per_dex, programs=programs, threshold=args.threshold)
    path = save_report(report, args.out)
    print(path.with_suffix(".md").read_text())
    print(f"report: {path}")
    notify(report)
    if report["alerts"]:
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(prog="dexray", description="DexRay — Solana DEX swap parser")
    sub = ap.add_subparsers(dest="command")

    p_parse = sub.add_parser("parse", help="Parse a single swap transaction")
    p_parse.add_argument("signature", help="Transaction signature")
    p_parse.add_argument("wallet", help="Wallet address")

    p_scan = sub.add_parser("scan", help="Scan a wallet's recent swaps")
    p_scan.add_argument("wallet", help="Wallet address")
    p_scan.add_argument("--limit", type=int, default=50, help="Max signatures to fetch (default: 50)")

    p_check = sub.add_parser("check", help="Sample live swaps per DEX and score the parser")
    p_check.add_argument("--per-dex", type=int, default=50, help="txs sampled per DEX (default: 50)")
    p_check.add_argument("--threshold", type=float, default=0.98, help="alert below this success rate")
    p_check.add_argument("--out", default="quality_reports", help="report directory (keeps history for trends)")
    p_check.add_argument("--rpc", action="append", help="RPC URL (repeatable; default: public mainnet)")
    p_check.add_argument("--rps", type=float, default=5, help="requests/sec per --rpc endpoint")
    p_check.add_argument("--dex", action="append", help=f"only these DEXes: {', '.join(DEX_PROGRAMS.values())}")

    args = ap.parse_args()
    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "check":
        cmd_check(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
