"""Multi-RPC client with round-robin rotation, failover, and batch support."""

import time
import requests
from typing import Any


_TX_PARAMS = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}


class _Provider:
    __slots__ = ("url", "rps", "last_request_time")

    def __init__(self, url: str, rps: float):
        self.url = url
        self.rps = rps
        self.last_request_time = 0.0

    def wait_if_needed(self) -> None:
        if self.rps <= 0:
            return
        interval = 1.0 / self.rps
        now = time.monotonic()
        wait = self.last_request_time + interval - now
        if wait > 0:
            time.sleep(wait)
        self.last_request_time = time.monotonic()


class MultiRPC:
    """Solana JSON-RPC client with multi-provider rotation and automatic failover."""

    def __init__(
        self,
        endpoints: list[str | dict],
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        self._providers: list[_Provider] = []
        for ep in endpoints:
            if isinstance(ep, dict):
                self._providers.append(_Provider(ep["url"], ep.get("rps", 0)))
            else:
                self._providers.append(_Provider(ep, 0))
        if not self._providers:
            raise ValueError("At least one endpoint is required")
        self._idx = 0
        self._max_retries = max_retries
        self._timeout = timeout
        self._session = requests.Session()

    def _next_provider(self) -> _Provider:
        p = self._providers[self._idx % len(self._providers)]
        self._idx += 1
        return p

    def _call(self, method: str, params: list[Any]) -> Any:
        """Execute a single JSON-RPC call with rotation and retry."""
        last_err: Exception | None = None
        n_providers = len(self._providers)

        for attempt in range(self._max_retries):
            for _ in range(n_providers):
                provider = self._next_provider()
                provider.wait_if_needed()
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                }
                try:
                    resp = self._session.post(
                        provider.url,
                        json=payload,
                        timeout=self._timeout,
                    )
                    if resp.status_code in (429, 500, 502, 503):
                        last_err = requests.HTTPError(
                            f"{resp.status_code} from {provider.url}"
                        )
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    if "error" in data:
                        last_err = RuntimeError(
                            f"RPC error: {data['error']}"
                        )
                        continue
                    return data.get("result")
                except requests.RequestException as e:
                    last_err = e
                    continue

            # All providers failed this round -- exponential backoff
            if attempt < self._max_retries - 1:
                time.sleep(2 ** attempt)

        raise ConnectionError(
            f"All providers failed after {self._max_retries} retries"
        ) from last_err

    def _batch_call(
        self, requests_list: list[dict],
    ) -> list[Any]:
        """Execute a batch JSON-RPC call with rotation and retry."""
        last_err: Exception | None = None
        n_providers = len(self._providers)

        for attempt in range(self._max_retries):
            for _ in range(n_providers):
                provider = self._next_provider()
                provider.wait_if_needed()
                try:
                    resp = self._session.post(
                        provider.url,
                        json=requests_list,
                        timeout=self._timeout,
                    )
                    if resp.status_code in (429, 500, 502, 503):
                        last_err = requests.HTTPError(
                            f"{resp.status_code} from {provider.url}"
                        )
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return data
                except requests.RequestException as e:
                    last_err = e
                    continue

            if attempt < self._max_retries - 1:
                time.sleep(2 ** attempt)

        raise ConnectionError(
            f"All providers failed after {self._max_retries} retries"
        ) from last_err

    def get_transaction(self, sig: str) -> dict | None:
        """Fetch a single transaction. Returns None if the transaction is not found."""
        result = self._call("getTransaction", [sig, _TX_PARAMS])
        return result  # None when tx not found

    def get_signatures(self, address: str, limit: int = 1000) -> list[dict]:
        """Fetch recent transaction signatures for an address."""
        return self._call(
            "getSignaturesForAddress",
            [address, {"limit": limit}],
        ) or []

    def batch_get_transactions(
        self, sigs: list[str], batch_size: int = 10,
    ) -> list[dict | None]:
        """Fetch multiple transactions in batched JSON-RPC calls."""
        results: list[dict | None] = []
        for i in range(0, len(sigs), batch_size):
            chunk = sigs[i : i + batch_size]
            payload = [
                {
                    "jsonrpc": "2.0",
                    "id": idx,
                    "method": "getTransaction",
                    "params": [sig, _TX_PARAMS],
                }
                for idx, sig in enumerate(chunk)
            ]
            batch_resp = self._batch_call(payload)
            # Sort by id to preserve order
            batch_resp.sort(key=lambda r: r.get("id", 0))
            for item in batch_resp:
                results.append(item.get("result"))
        return results
