"""Token metadata resolver: symbol lookup with memory + file cache."""

from __future__ import annotations

import json
from pathlib import Path

import requests


_JUPITER_STRICT_URL = "https://token.jup.ag/strict"
_CACHE_DIR = Path.home() / ".dexray"
_CACHE_FILE = _CACHE_DIR / "token_cache.json"


class TokenResolver:
    """Resolve token mint addresses to symbols with caching."""

    def __init__(self, preload: bool = True, cache_file: Path | None = None):
        self._cache: dict[str, str] = {}
        self._cache_file = cache_file or _CACHE_FILE
        self._all_loaded = False
        self._load_file_cache()
        if preload:
            self._preload_jupiter()

    def _load_file_cache(self) -> None:
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text())
                if isinstance(data, dict):
                    self._cache.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    def _save_file_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(json.dumps(self._cache))
        except OSError:
            pass

    def _preload_jupiter(self) -> None:
        try:
            resp = requests.get(_JUPITER_STRICT_URL, timeout=10)
            resp.raise_for_status()
            tokens = resp.json()
            for token in tokens:
                mint = token.get("address", "")
                symbol = token.get("symbol", "")
                if mint and symbol:
                    self._cache[mint] = symbol
            self._save_file_cache()
        except Exception:
            pass

    def resolve(self, mint: str) -> str:
        """Return the symbol for a mint address, or the mint itself if unknown."""
        if mint in self._cache:
            return self._cache[mint]

        # Lazy lookup via Jupiter all-tokens API
        symbol = self._fetch_single(mint)
        if symbol:
            self._cache[mint] = symbol
            self._save_file_cache()
            return symbol

        return mint

    def _fetch_single(self, mint: str) -> str | None:
        if self._all_loaded:
            return None
        try:
            resp = requests.get(
                "https://token.jup.ag/all",
                timeout=30,
            )
            resp.raise_for_status()
            for token in resp.json():
                addr = token.get("address", "")
                sym = token.get("symbol", "")
                if addr and sym:
                    self._cache[addr] = sym
            self._all_loaded = True
            self._save_file_cache()
            return self._cache.get(mint)
        except Exception:
            return None

    def batch_resolve(self, mints: list[str]) -> dict[str, str]:
        """Resolve multiple mints at once."""
        return {mint: self.resolve(mint) for mint in mints}

    def add(self, mint: str, symbol: str) -> None:
        """Manually add a mint-symbol mapping."""
        self._cache[mint] = symbol
        self._save_file_cache()
