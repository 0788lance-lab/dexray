"""Save a real mainnet transaction as a regression fixture.

Every parser fix ships with the transaction it got wrong:

    python scripts/add_fixture.py <signature> --name usdc_relayer_sell \
        --note "USDC amount had float noise (31.584113999999985)" [--wallet <trader>]

The fixture pins the *current* parse output as the expected result, so run it
after the fix and check the printed output against the raw balance changes
before committing. Omit --wallet to pin the inferred trader instead.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dexray.solana.parser import parse_swap  # noqa: E402
from dexray.solana.quality import raw_changes, verify_swap  # noqa: E402
from dexray.solana.rpc import MultiRPC  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "regression"
EXPECTED_FIELDS = (
    "direction", "mint", "token_amount", "quote_mint", "quote_amount",
    "sol_amount", "usdc_amount", "trader", "fee_payer", "source",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signature")
    ap.add_argument("--name", required=True, help="short snake_case label, e.g. usdc_relayer_sell")
    ap.add_argument("--note", required=True, help="what went wrong / what this tx guards")
    ap.add_argument("--wallet", help="trader to parse for (default: inferred)")
    ap.add_argument("--rpc", action="append", help="RPC URL (repeatable; default: public mainnet)")
    args = ap.parse_args()

    tx = MultiRPC(args.rpc).get_transaction(args.signature)
    if tx is None:
        sys.exit("transaction not found")

    swap = parse_swap(tx, args.wallet)
    expected = {f: getattr(swap, f) for f in EXPECTED_FIELDS} if swap else None
    trader = args.wallet or (swap.trader if swap else None)

    print(f"version: {tx.get('version')}")
    if trader:
        print(f"raw balance changes of {trader}:")
        for mint, (delta, decimals) in raw_changes(tx, trader).items():
            print(f"  {mint}: {delta} (decimals {decimals})")
    print("expected:", json.dumps(expected, indent=2))
    if swap and verify_swap(tx, swap):
        print("WARNING: parse disagrees with raw balances:", verify_swap(tx, swap))

    path = FIXTURE_DIR / f"{args.name}_{args.signature[:8]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "sig": args.signature,
        "wallet": args.wallet,
        "note": args.note,
        "expected": expected,
        "tx": tx,
    }, indent=1) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
