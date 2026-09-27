"""Tests for MultiRPC client: rotation, failover, batch, rate limiting."""

import json
import time
from unittest.mock import patch, MagicMock

import pytest

from dexray.solana.rpc import MultiRPC, _Provider


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ok_response(result, status=200, req_id=1):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"jsonrpc": "2.0", "id": req_id, "result": result}
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(status):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock(
        side_effect=Exception(f"HTTP {status}")
    )
    return resp


def _rpc_error_response(code=-32600, message="Invalid request"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": code, "message": message},
    }
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------

class TestMultiRPCInit:
    def test_string_endpoints(self):
        rpc = MultiRPC(["http://a", "http://b"])
        assert len(rpc._providers) == 2

    def test_dict_endpoints(self):
        rpc = MultiRPC([{"url": "http://a", "rps": 10}])
        assert rpc._providers[0].rps == 10

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            MultiRPC([])


# ---------------------------------------------------------------------------
# round-robin rotation
# ---------------------------------------------------------------------------

class TestRotation:
    @patch("dexray.solana.rpc.requests.Session")
    def test_round_robin(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        urls_called = []

        def capture_post(url, **kw):
            urls_called.append(url)
            return _ok_response({"value": True})

        session.post = capture_post

        rpc = MultiRPC(["http://a", "http://b", "http://c"])
        rpc.get_transaction("sig1")
        rpc.get_transaction("sig2")
        rpc.get_transaction("sig3")

        assert urls_called == ["http://a", "http://b", "http://c"]


# ---------------------------------------------------------------------------
# failover
# ---------------------------------------------------------------------------

class TestFailover:
    @patch("dexray.solana.rpc.requests.Session")
    def test_429_switches_provider(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        call_count = 0

        def side_effect(url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _error_response(429)
            return _ok_response({"some": "data"})

        session.post = side_effect

        rpc = MultiRPC(["http://a", "http://b"], max_retries=1)
        result = rpc.get_transaction("sig")
        assert result == {"some": "data"}
        assert call_count == 2

    @patch("dexray.solana.rpc.requests.Session")
    def test_500_switches_provider(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        call_count = 0

        def side_effect(url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _error_response(500)
            return _ok_response({"some": "data"})

        session.post = side_effect

        rpc = MultiRPC(["http://a", "http://b"], max_retries=1)
        result = rpc.get_transaction("sig")
        assert result == {"some": "data"}

    @patch("dexray.solana.rpc.requests.Session")
    @patch("dexray.solana.rpc.time.sleep")
    def test_all_fail_raises(self, mock_sleep, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.post = lambda url, **kw: _error_response(429)

        rpc = MultiRPC(["http://a"], max_retries=2)
        with pytest.raises(ConnectionError, match="All providers failed"):
            rpc.get_transaction("sig")

    @patch("dexray.solana.rpc.requests.Session")
    def test_rpc_error_switches(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        call_count = 0

        def side_effect(url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _rpc_error_response()
            return _ok_response({"ok": True})

        session.post = side_effect

        rpc = MultiRPC(["http://a", "http://b"], max_retries=1)
        result = rpc.get_transaction("sig")
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# get_transaction
# ---------------------------------------------------------------------------

class TestGetTransaction:
    @patch("dexray.solana.rpc.requests.Session")
    def test_returns_result(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.post = lambda url, **kw: _ok_response({"slot": 123})

        rpc = MultiRPC(["http://a"])
        assert rpc.get_transaction("sig") == {"slot": 123}

    @patch("dexray.solana.rpc.requests.Session")
    def test_returns_none_for_null_result(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.post = lambda url, **kw: _ok_response(None)

        rpc = MultiRPC(["http://a"])
        assert rpc.get_transaction("sig") is None

    @patch("dexray.solana.rpc.requests.Session")
    def test_passes_json_parsed_params(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        captured = {}

        def capture(url, **kw):
            captured["payload"] = kw.get("json")
            return _ok_response(None)

        session.post = capture

        rpc = MultiRPC(["http://a"])
        rpc.get_transaction("mysig")

        payload = captured["payload"]
        assert payload["method"] == "getTransaction"
        params = payload["params"]
        assert params[0] == "mysig"
        assert params[1]["encoding"] == "jsonParsed"
        assert params[1]["maxSupportedTransactionVersion"] == 0


# ---------------------------------------------------------------------------
# get_signatures
# ---------------------------------------------------------------------------

class TestGetSignatures:
    @patch("dexray.solana.rpc.requests.Session")
    def test_returns_list(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        sigs = [{"signature": "s1"}, {"signature": "s2"}]
        session.post = lambda url, **kw: _ok_response(sigs)

        rpc = MultiRPC(["http://a"])
        result = rpc.get_signatures("wallet", limit=10)
        assert result == sigs

    @patch("dexray.solana.rpc.requests.Session")
    def test_uses_correct_method(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        captured = {}

        def capture(url, **kw):
            captured["payload"] = kw.get("json")
            return _ok_response([])

        session.post = capture

        rpc = MultiRPC(["http://a"])
        rpc.get_signatures("addr123", limit=50)

        payload = captured["payload"]
        assert payload["method"] == "getSignaturesForAddress"
        assert payload["params"][0] == "addr123"
        assert payload["params"][1]["limit"] == 50

    @patch("dexray.solana.rpc.requests.Session")
    def test_returns_empty_on_none(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.post = lambda url, **kw: _ok_response(None)

        rpc = MultiRPC(["http://a"])
        assert rpc.get_signatures("addr") == []


# ---------------------------------------------------------------------------
# batch_get_transactions
# ---------------------------------------------------------------------------

class TestBatchGetTransactions:
    @patch("dexray.solana.rpc.requests.Session")
    def test_batch_returns_ordered_results(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        def batch_response(url, **kw):
            payload = kw.get("json")
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            results = []
            for item in payload:
                results.append({
                    "jsonrpc": "2.0",
                    "id": item["id"],
                    "result": {"sig": item["params"][0]},
                })
            resp.json.return_value = results
            return resp

        session.post = batch_response

        rpc = MultiRPC(["http://a"])
        results = rpc.batch_get_transactions(["s1", "s2", "s3"], batch_size=10)
        assert len(results) == 3
        assert results[0] == {"sig": "s1"}
        assert results[1] == {"sig": "s2"}
        assert results[2] == {"sig": "s3"}

    @patch("dexray.solana.rpc.requests.Session")
    def test_batch_chunking(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        call_count = 0

        def batch_response(url, **kw):
            nonlocal call_count
            call_count += 1
            payload = kw.get("json")
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            results = [
                {"jsonrpc": "2.0", "id": item["id"], "result": None}
                for item in payload
            ]
            resp.json.return_value = results
            return resp

        session.post = batch_response

        rpc = MultiRPC(["http://a"])
        sigs = [f"s{i}" for i in range(25)]
        results = rpc.batch_get_transactions(sigs, batch_size=10)
        assert len(results) == 25
        assert call_count == 3  # 10 + 10 + 5

    @patch("dexray.solana.rpc.requests.Session")
    def test_batch_preserves_none(self, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session

        def batch_response(url, **kw):
            payload = kw.get("json")
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            results = []
            for item in payload:
                r = {"sig": item["params"][0]} if item["id"] % 2 == 0 else None
                results.append({"jsonrpc": "2.0", "id": item["id"], "result": r})
            resp.json.return_value = results
            return resp

        session.post = batch_response

        rpc = MultiRPC(["http://a"])
        results = rpc.batch_get_transactions(["s0", "s1", "s2"], batch_size=10)
        assert results[0] == {"sig": "s0"}
        assert results[1] is None
        assert results[2] == {"sig": "s2"}


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    def test_provider_wait(self):
        p = _Provider("http://a", rps=100)
        p.last_request_time = time.monotonic()
        start = time.monotonic()
        p.wait_if_needed()
        elapsed = time.monotonic() - start
        # Should wait at most 10ms for 100 rps
        assert elapsed < 0.02

    def test_provider_no_limit(self):
        p = _Provider("http://a", rps=0)
        p.wait_if_needed()  # should not sleep


# ---------------------------------------------------------------------------
# exponential backoff
# ---------------------------------------------------------------------------

class TestBackoff:
    @patch("dexray.solana.rpc.requests.Session")
    @patch("dexray.solana.rpc.time.sleep")
    def test_backoff_between_retries(self, mock_sleep, mock_session_cls):
        session = MagicMock()
        mock_session_cls.return_value = session
        session.post = lambda url, **kw: _error_response(429)

        rpc = MultiRPC(["http://a"], max_retries=3)
        with pytest.raises(ConnectionError):
            rpc.get_transaction("sig")

        # Should have slept between retry rounds: 2^0=1, 2^1=2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
