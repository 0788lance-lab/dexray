"""Helius Enhanced API compatibility layer."""

from __future__ import annotations

from dexray.core import Swap
from dexray.solana.parser import parse_swap, LAMPORTS_PER_SOL, WSOL


def to_helius_format(swap: Swap) -> dict:
    """Convert a DexRay Swap into Helius Enhanced Transaction-like dict.

    Field mapping follows docs/MIGRATION.md.
    """
    native_amount = int(round(swap.sol_amount * LAMPORTS_PER_SOL))
    # Non-SOL quote leg (USDC, USDT, or the other token of a token-to-token swap)
    quote_leg = None
    if swap.quote_mint and swap.quote_mint != WSOL and swap.quote_amount > 0:
        quote_leg = {
            "fromUserAccount": "",
            "toUserAccount": "",
            "mint": swap.quote_mint,
            "tokenAmount": swap.quote_amount,
            "tokenStandard": "Fungible",
        }

    token_transfers = []
    if swap.direction == "BUY":
        if quote_leg:
            token_transfers.append(quote_leg)
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
        if quote_leg:
            token_transfers.append(quote_leg)
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

    if quote_leg:
        quote_token = {
            "userAccount": "",
            "tokenAccount": "",
            "mint": swap.quote_mint,
            "rawTokenAmount": {
                "tokenAmount": str(swap.quote_amount),
                "decimals": 0,
            },
        }
        if swap.direction == "BUY":
            token_input = quote_token
        else:
            token_output = quote_token

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
        "feePayer": swap.fee_payer,
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
