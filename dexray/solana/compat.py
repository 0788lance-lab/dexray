"""Helius Enhanced API compatibility layer."""

from __future__ import annotations

from dexray.core import Swap
from dexray.solana.parser import parse_swap, LAMPORTS_PER_SOL


def to_helius_format(swap: Swap) -> dict:
    """Convert a DexRay Swap into Helius Enhanced Transaction-like dict.

    Field mapping follows docs/MIGRATION.md.
    """
    native_amount = int(swap.sol_amount * LAMPORTS_PER_SOL)

    token_transfers = []
    if swap.direction == "BUY":
        if swap.sol_amount > 0:
            token_transfers.append({
                "fromUserAccount": "",
                "toUserAccount": "",
                "mint": "So11111111111111111111111111111111111111112",
                "tokenAmount": swap.sol_amount,
                "tokenStandard": "Native",
            })
        token_transfers.append({
            "fromUserAccount": "",
            "toUserAccount": "",
            "mint": swap.mint,
            "tokenAmount": swap.token_amount,
            "tokenStandard": "Fungible",
        })
    else:  # SELL
        token_transfers.append({
            "fromUserAccount": "",
            "toUserAccount": "",
            "mint": swap.mint,
            "tokenAmount": swap.token_amount,
            "tokenStandard": "Fungible",
        })
        if swap.sol_amount > 0:
            token_transfers.append({
                "fromUserAccount": "",
                "toUserAccount": "",
                "mint": "So11111111111111111111111111111111111111112",
                "tokenAmount": swap.sol_amount,
                "tokenStandard": "Native",
            })

    native_input = None
    native_output = None
    if swap.direction == "BUY" and swap.sol_amount > 0:
        native_input = {
            "account": "",
            "amount": str(native_amount),
        }
    elif swap.direction == "SELL" and swap.sol_amount > 0:
        native_output = {
            "account": "",
            "amount": str(native_amount),
        }

    token_input = None
    token_output = None
    if swap.direction == "BUY":
        token_output = {
            "userAccount": "",
            "tokenAccount": "",
            "mint": swap.mint,
            "rawTokenAmount": {
                "tokenAmount": str(swap.token_amount),
                "decimals": 0,
            },
        }
    else:
        token_input = {
            "userAccount": "",
            "tokenAccount": "",
            "mint": swap.mint,
            "rawTokenAmount": {
                "tokenAmount": str(swap.token_amount),
                "decimals": 0,
            },
        }

    swap_event = {}
    if native_input:
        swap_event["nativeInput"] = native_input
    if native_output:
        swap_event["nativeOutput"] = native_output
    if token_input:
        swap_event["tokenInputs"] = [token_input]
    if token_output:
        swap_event["tokenOutputs"] = [token_output]

    return {
        "type": "SWAP",
        "source": swap.source,
        "signature": swap.signature,
        "timestamp": swap.timestamp,
        "tokenTransfers": token_transfers,
        "events": {
            "swap": swap_event,
        },
    }


def swap_from_tx(tx: dict, wallet: str) -> dict | None:
    """Parse a raw transaction and return Helius-compatible dict, or None."""
    swap = parse_swap(tx, wallet)
    if swap is None:
        return None
    return to_helius_format(swap)
