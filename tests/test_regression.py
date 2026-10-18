"""Regression suite: real mainnet transactions the parser once got wrong.

Each fixture in fixtures/regression/ pins the expected parse of one real tx
(see scripts/add_fixture.py). Every parser fix must add the tx it fixed.
"""

import json
from pathlib import Path

import pytest

from dexray.solana.parser import parse_swap
from dexray.solana.quality import swapping_signers, verify_swap

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "regression").glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_expected_parse(path):
    fx = _load(path)
    swap = parse_swap(fx["tx"], fx["wallet"])
    if fx["expected"] is None:
        assert swap is None, fx["note"]
        return
    assert swap is not None, fx["note"]
    for field, want in fx["expected"].items():
        assert getattr(swap, field) == want, f"{field}: {fx['note']}"


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_matches_raw_balances(path):
    """Independent check: amounts and direction agree with integer pre/post balances."""
    fx = _load(path)
    swap = parse_swap(fx["tx"], fx["wallet"])
    if swap is not None:
        assert verify_swap(fx["tx"], swap) == []


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_inferred_trader(path):
    """Without a wallet, the parser attributes the swap to a signer that swapped:
    the expected trader, unless the tx bundles several traders."""
    fx = _load(path)
    if fx["expected"] is None:
        return
    swap = parse_swap(fx["tx"])
    assert swap is not None
    swappers = swapping_signers(fx["tx"])
    assert swap.trader in swappers
    if len(swappers) == 1:
        assert swap.trader == fx["expected"]["trader"]


def test_suite_covers_tx_versions():
    versions = {_load(p)["tx"].get("version") for p in FIXTURES}
    assert {"legacy", 0, 1} <= versions
