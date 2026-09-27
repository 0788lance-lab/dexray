"""Integration tests using real transaction fixtures."""

import json
import os
from pathlib import Path

import pytest

from dexray.solana.parser import parse_swap

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> tuple[dict, str]:
    """Load a fixture file, return (tx, wallet)."""
    with open(FIXTURES_DIR / name) as f:
        data = json.load(f)
    return data["tx"], data["wallet"]


class TestJupiterBuy:
    def test_jupiter_sol_to_token(self):
        """Jupiter BUY: SOL spent, token received."""
        tx, wallet = load_fixture("jupiter_swap_29SX7Qi7.json")
        swap = parse_swap(tx, wallet)

        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.sol_amount > 0
        assert swap.token_amount > 0
        assert swap.source == "JUPITER"
        # From our analysis: SOL change = -0.03, token delta = +12899
        assert abs(swap.sol_amount - 0.03) < 0.001
        assert abs(swap.token_amount - 12899.008387) < 1.0
        assert swap.timestamp == 1790481133


class TestFailedTransactions:
    def test_failed_jupiter_1(self):
        tx, wallet = load_fixture("jupiter_swap_2jaxQ5vN.json")
        swap = parse_swap(tx, wallet)
        assert swap is None

    def test_failed_jupiter_2(self):
        tx, wallet = load_fixture("jupiter_swap_4PTrUssK.json")
        swap = parse_swap(tx, wallet)
        assert swap is None


class TestPumpSwapBuy:
    def test_pumpswap_buy_new_ata(self):
        """PumpSwap BUY with new ATA creation (token only in post)."""
        tx, wallet = load_fixture("pumpswap_3GnMkq8o.json")
        swap = parse_swap(tx, wallet)

        assert swap is not None
        assert swap.direction == "BUY"
        assert swap.sol_amount > 1.0
        assert swap.token_amount > 100000
        assert swap.source == "PUMPSWAP"
        assert swap.timestamp == 1790481167


class TestRaydiumSell:
    def test_raydium_sell(self):
        """Raydium SELL: token sent, SOL received."""
        tx, wallet = load_fixture("raydium_5s17quVE.json")
        swap = parse_swap(tx, wallet)

        assert swap is not None
        assert swap.direction == "SELL"
        assert swap.sol_amount > 3.0
        assert swap.token_amount > 400000
        # DEX should be detected from inner instructions
        assert swap.source in ("RAYDIUM", "RAYDIUM_CPMM", "RAYDIUM_CLMM")
        assert swap.timestamp == 1790481165


class TestNonSwap:
    def test_sol_transfer_not_swap(self):
        """Plain SOL transfer should not be detected as a swap."""
        tx, wallet = load_fixture("non_swap_transfer.json")
        swap = parse_swap(tx, wallet)
        assert swap is None


class TestAllFixtures:
    def test_no_exceptions(self):
        """parse_swap should never raise on any fixture -- it returns None or Swap."""
        for fname in os.listdir(FIXTURES_DIR):
            if not fname.endswith(".json"):
                continue
            tx, wallet = load_fixture(fname)
            try:
                result = parse_swap(tx, wallet)
                assert result is None or isinstance(result, object)
            except Exception as e:
                pytest.fail(f"parse_swap raised on {fname}: {e}")

    def test_swap_data_completeness(self):
        """Every detected swap must have all required fields populated."""
        for fname in os.listdir(FIXTURES_DIR):
            if not fname.endswith(".json"):
                continue
            tx, wallet = load_fixture(fname)
            swap = parse_swap(tx, wallet)
            if swap is None:
                continue

            assert swap.direction in ("BUY", "SELL"), f"{fname}: bad direction"
            assert len(swap.mint) > 10, f"{fname}: mint too short"
            assert swap.token_amount > 0, f"{fname}: no token amount"
            assert swap.sol_amount > 0 or swap.usdc_amount > 0, \
                f"{fname}: no sol or usdc amount"
            assert swap.timestamp > 0, f"{fname}: no timestamp"
            assert len(swap.signature) > 10, f"{fname}: no signature"
