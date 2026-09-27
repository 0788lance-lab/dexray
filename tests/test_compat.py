"""Tests for Helius compatibility layer."""

import pytest

from dexray.core import Swap
from dexray.solana.compat import to_helius_format, swap_from_tx


def _make_buy_swap() -> Swap:
    return Swap(
        direction="BUY",
        mint="TokenMint123",
        symbol="TEST",
        sol_amount=0.5,
        usdc_amount=0.0,
        token_amount=10000.0,
        timestamp=1700000000,
        signature="buysig123",
        source="JUPITER",
        program="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    )


def _make_sell_swap() -> Swap:
    return Swap(
        direction="SELL",
        mint="TokenMint456",
        symbol="TEST2",
        sol_amount=1.5,
        usdc_amount=0.0,
        token_amount=50000.0,
        timestamp=1700001000,
        signature="sellsig456",
        source="RAYDIUM",
        program="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    )


def _make_usdc_buy_swap() -> Swap:
    return Swap(
        direction="BUY",
        mint="TokenMint789",
        symbol="MEME",
        sol_amount=0.0,
        usdc_amount=100.0,
        token_amount=500000.0,
        timestamp=1700002000,
        signature="usdcbuysig789",
        source="JUPITER",
        program="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    )


class TestToHeliusFormat:
    def test_buy_structure(self):
        result = to_helius_format(_make_buy_swap())

        assert result["type"] == "SWAP"
        assert result["source"] == "JUPITER"
        assert result["signature"] == "buysig123"
        assert result["timestamp"] == 1700000000

    def test_buy_swap_event(self):
        result = to_helius_format(_make_buy_swap())
        swap_event = result["events"]["swap"]

        assert "nativeInput" in swap_event
        assert swap_event["nativeInput"]["amount"] == "500000000"
        assert "tokenOutputs" in swap_event
        assert swap_event["tokenOutputs"][0]["mint"] == "TokenMint123"

    def test_sell_structure(self):
        result = to_helius_format(_make_sell_swap())

        assert result["type"] == "SWAP"
        assert result["source"] == "RAYDIUM"
        assert result["signature"] == "sellsig456"

    def test_sell_swap_event(self):
        result = to_helius_format(_make_sell_swap())
        swap_event = result["events"]["swap"]

        assert "nativeOutput" in swap_event
        assert swap_event["nativeOutput"]["amount"] == "1500000000"
        assert "tokenInputs" in swap_event
        assert swap_event["tokenInputs"][0]["mint"] == "TokenMint456"

    def test_buy_token_transfers(self):
        result = to_helius_format(_make_buy_swap())
        transfers = result["tokenTransfers"]

        assert len(transfers) == 2
        mints = [t["mint"] for t in transfers]
        assert "So11111111111111111111111111111111111111112" in mints
        assert "TokenMint123" in mints

    def test_sell_token_transfers(self):
        result = to_helius_format(_make_sell_swap())
        transfers = result["tokenTransfers"]

        assert len(transfers) == 2
        mints = [t["mint"] for t in transfers]
        assert "TokenMint456" in mints
        assert "So11111111111111111111111111111111111111112" in mints

    def test_usdc_buy_no_native(self):
        result = to_helius_format(_make_usdc_buy_swap())
        swap_event = result["events"]["swap"]

        assert "nativeInput" not in swap_event
        assert "nativeOutput" not in swap_event
        assert "tokenOutputs" in swap_event

        # Token transfers should only contain the target token (no SOL)
        transfers = result["tokenTransfers"]
        assert len(transfers) == 1
        assert transfers[0]["mint"] == "TokenMint789"


class TestSwapFromTx:
    def test_returns_dict_for_swap(self):
        tx = {
            "blockTime": 1700000000,
            "transaction": {
                "signatures": ["sig123"],
                "message": {
                    "accountKeys": ["WalletABC"],
                    "instructions": [{"programId": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"}],
                },
            },
            "meta": {
                "err": None,
                "fee": 5000,
                "preBalances": [1000000000],
                "postBalances": [500000000],
                "preTokenBalances": [],
                "postTokenBalances": [
                    {
                        "accountIndex": 1,
                        "owner": "WalletABC",
                        "mint": "TokenMintXYZ",
                        "uiTokenAmount": {
                            "uiAmount": 1000.0,
                            "uiAmountString": "1000.0",
                            "decimals": 6,
                            "amount": "1000000000",
                        },
                    }
                ],
                "innerInstructions": [],
            },
        }
        result = swap_from_tx(tx, "WalletABC")
        assert result is not None
        assert result["type"] == "SWAP"
        assert result["source"] == "JUPITER"

    def test_returns_none_for_non_swap(self):
        tx = {
            "blockTime": 1700000000,
            "transaction": {
                "signatures": ["sig123"],
                "message": {
                    "accountKeys": ["WalletABC"],
                    "instructions": [],
                },
            },
            "meta": {
                "err": None,
                "fee": 5000,
                "preBalances": [1000000000],
                "postBalances": [500000000],
                "preTokenBalances": [],
                "postTokenBalances": [],
                "innerInstructions": [],
            },
        }
        result = swap_from_tx(tx, "WalletABC")
        assert result is None

    def test_returns_none_for_failed(self):
        tx = {
            "blockTime": 1700000000,
            "transaction": {
                "signatures": ["sig123"],
                "message": {
                    "accountKeys": ["WalletABC"],
                    "instructions": [],
                },
            },
            "meta": {
                "err": {"InstructionError": [0, "Custom"]},
                "fee": 5000,
                "preBalances": [1000000000],
                "postBalances": [1000000000],
                "preTokenBalances": [],
                "postTokenBalances": [],
                "innerInstructions": [],
            },
        }
        result = swap_from_tx(tx, "WalletABC")
        assert result is None
