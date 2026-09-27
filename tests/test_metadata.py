"""Tests for token metadata resolver: caching, preload, fallback."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from dexray.solana.metadata import TokenResolver


SAMPLE_JUPITER_RESPONSE = [
    {"address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
    {"address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "symbol": "USDT"},
    {"address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "symbol": "BONK"},
]


def _mock_get_success(url, **kw):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = SAMPLE_JUPITER_RESPONSE
    return resp


def _mock_get_fail(url, **kw):
    raise Exception("Network error")


class TestPreload:
    @patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_success)
    def test_preload_populates_cache(self, mock_get):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            resolver = TokenResolver(preload=True, cache_file=cache_file)

            assert resolver.resolve("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") == "USDC"
            assert resolver.resolve("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263") == "BONK"

    @patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_fail)
    def test_preload_failure_graceful(self, mock_get):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            resolver = TokenResolver(preload=True, cache_file=cache_file)
            # Should not raise, just have empty cache
            assert resolver.resolve("UnknownMint123") == "UnknownMint123"


class TestFileCache:
    def test_saves_and_loads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"

            with patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_success):
                resolver1 = TokenResolver(preload=True, cache_file=cache_file)

            assert cache_file.exists()

            with patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_fail):
                resolver2 = TokenResolver(preload=False, cache_file=cache_file)

            # Should still resolve from file cache
            assert resolver2.resolve("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") == "USDC"

    def test_corrupted_cache_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            cache_file.write_text("not valid json{{{")

            with patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_fail):
                resolver = TokenResolver(preload=False, cache_file=cache_file)
                assert resolver.resolve("Mint123") == "Mint123"


class TestResolve:
    @patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_success)
    def test_known_mint(self, mock_get):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            resolver = TokenResolver(preload=True, cache_file=cache_file)
            assert resolver.resolve("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB") == "USDT"

    @patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_fail)
    def test_unknown_mint_returns_address(self, mock_get):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            resolver = TokenResolver(preload=False, cache_file=cache_file)
            result = resolver.resolve("UnknownMint999")
            assert result == "UnknownMint999"


class TestManualAdd:
    def test_add_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"

            with patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_fail):
                resolver = TokenResolver(preload=False, cache_file=cache_file)
                resolver.add("CustomMint123", "CUSTOM")
                assert resolver.resolve("CustomMint123") == "CUSTOM"

            # Verify persisted
            data = json.loads(cache_file.read_text())
            assert data["CustomMint123"] == "CUSTOM"


class TestBatchResolve:
    @patch("dexray.solana.metadata.requests.get", side_effect=_mock_get_success)
    def test_batch(self, mock_get):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            resolver = TokenResolver(preload=True, cache_file=cache_file)
            results = resolver.batch_resolve([
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "Unknown123",
            ])
            assert results["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"] == "USDC"
            assert results["Unknown123"] == "Unknown123"
