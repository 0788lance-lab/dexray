"""Tests for the data-quality checker, driven by real regression fixtures."""

import dataclasses
import json
from pathlib import Path

from dexray.solana.parser import parse_swap
from dexray.solana.quality import (
    check_dex,
    looks_like_swap,
    render_markdown,
    run_check,
    save_report,
    load_history,
    swapping_signers,
    verify_swap,
)

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "regression").glob("*.json"))
TXS = {json.loads(p.read_text())["sig"]: json.loads(p.read_text())["tx"] for p in FIXTURES}
SWAP_SIGS = [s for s, tx in TXS.items() if parse_swap(tx) is not None]
PROGRAM = "DexProgram1111"


class FakeRPC:
    def __init__(self, txs, refuse=()):
        self.txs = txs
        self.refuse = set(refuse)

    def get_signatures(self, address, limit=1000):
        return [{"signature": s, "err": None} for s in self.txs]

    def get_transaction(self, sig):
        if sig in self.refuse:
            try:
                raise RuntimeError("RPC error: {'code': -32015, 'message': 'Transaction version (1) is not supported'}")
            except RuntimeError as e:
                raise ConnectionError("All providers failed after 3 retries") from e
        return self.txs.get(sig)


def _flip_direction(tx):
    swap = parse_swap(tx)
    if swap is None:
        return None
    return dataclasses.replace(swap, direction="SELL" if swap.direction == "BUY" else "BUY")


def _drop_decimal(tx):
    swap = parse_swap(tx)
    return swap and dataclasses.replace(swap, quote_amount=swap.quote_amount * 10)


class TestOracle:
    def test_fixture_swaps_verify(self):
        for sig in SWAP_SIGS:
            assert verify_swap(TXS[sig], parse_swap(TXS[sig])) == [], sig

    def test_oracle_agrees_with_parser(self):
        for sig, tx in TXS.items():
            swap = parse_swap(tx)
            assert (looks_like_swap(tx) is not None) == (swap is not None), sig
            if swap:
                assert swap.trader in swapping_signers(tx)

    def test_bundle_has_two_swappers(self):
        sig = next(s for s in TXS if s.startswith("VqpeoCEp"))
        assert len(swapping_signers(TXS[sig])) == 2

    def test_catches_wrong_direction(self):
        tx = TXS[SWAP_SIGS[0]]
        problems = verify_swap(tx, _flip_direction(tx))
        assert any("direction" in p for p in problems)

    def test_catches_wrong_amount(self):
        tx = TXS[SWAP_SIGS[0]]
        assert any("quote_amount" in p for p in verify_swap(tx, _drop_decimal(tx)))

    def test_catches_fee_payer_as_trader(self):
        sig = next(s for s in SWAP_SIGS if parse_swap(TXS[s]).fee_payer != parse_swap(TXS[s]).trader)
        swap = parse_swap(TXS[sig])
        wrong = dataclasses.replace(swap, trader=swap.fee_payer)
        assert verify_swap(TXS[sig], wrong) != []


class TestCheck:
    def test_healthy_parser_passes(self):
        res = check_dex(FakeRPC(TXS), PROGRAM, "DEX", per_dex=len(TXS))
        assert res.swaps == len(SWAP_SIGS)
        assert res.success_rate == 1.0
        assert not (res.missed or res.wrong or res.spurious or res.exceptions)

    def test_broken_direction_alerts(self):
        report = run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"}, parse_fn=_flip_direction)
        assert report["dexes"][0]["success_rate"] == 0.0
        assert report["alerts"]

    def test_missed_swaps_alert(self):
        report = run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"}, parse_fn=lambda tx: None)
        assert len(report["dexes"][0]["missed"]) == len(SWAP_SIGS)
        assert report["alerts"]

    def test_parser_exception_alerts(self):
        def boom(tx):
            raise KeyError("accountKeys")
        report = run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"}, parse_fn=boom)
        assert report["dexes"][0]["exceptions"]
        assert report["alerts"]

    def test_rpc_refusal_counts_as_failure(self):
        """An unsupported tx version must lower the rate, not vanish from the sample."""
        rpc = FakeRPC(TXS, refuse=[s for s, tx in TXS.items() if tx.get("version") == 1])
        report = run_check(rpc, per_dex=len(TXS), programs={PROGRAM: "DEX"})
        assert report["dexes"][0]["rpc_errors"]
        assert report["alerts"]


class TestAlertRules:
    def test_single_wrong_parse_alerts_above_threshold(self):
        target = SWAP_SIGS[0]

        def one_wrong(tx):
            swap = parse_swap(tx)
            if swap and swap.signature == target:
                return dataclasses.replace(swap, quote_amount=swap.quote_amount + 1e-5)
            return swap
        report = run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"},
                           parse_fn=one_wrong, threshold=0.5)
        assert report["dexes"][0]["success_rate"] > 0.5
        assert any("wrong parse" in a for a in report["alerts"])


class TestSampling:
    def test_no_signatures_alerts(self):
        report = run_check(FakeRPC({}), per_dex=10, programs={PROGRAM: "DEX"})
        assert any("no recent transactions" in a for a in report["alerts"])

    def test_low_sample_warns_without_alert(self):
        few = dict(list(TXS.items())[:3])
        report = run_check(FakeRPC(few), per_dex=50, programs={PROGRAM: "DEX"})
        assert report["warnings"]
        assert not report["alerts"]

    def test_stops_at_target(self):
        res = check_dex(FakeRPC(TXS), PROGRAM, "DEX", per_dex=3)
        assert res.scored == 3

    def test_fetch_budget(self):
        res = check_dex(FakeRPC(TXS), PROGRAM, "DEX", per_dex=50, max_fetch=4)
        assert res.sampled == 4


class TestReport:
    def test_save_and_trend(self, tmp_path):
        r1 = run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"})
        save_report(r1, tmp_path)
        r2 = dict(run_check(FakeRPC(TXS), per_dex=len(TXS), programs={PROGRAM: "DEX"},
                            parse_fn=_flip_direction), time=r1["time"] + 7 * 86400)
        save_report(r2, tmp_path)
        assert len(load_history(tmp_path)) == 2
        md = render_markdown(r2, load_history(tmp_path))
        assert "ALERTS" in md
        assert "| DEX | 100.0% | 0.0% |" in md
