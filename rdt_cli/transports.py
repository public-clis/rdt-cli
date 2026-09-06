"""HTTP transports for read and write Reddit requests."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

from .config import RuntimeConfig
from .constants import BASE_URL
from .exceptions import (
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    RedditApiError,
    SessionExpiredError,
)
from .fingerprint import BrowserFingerprint
from .session import SessionState

logger = logging.getLogger(__name__)


class BaseTransport:
    """Shared retry, throttling, and cookie management."""

    def __init__(
        self,
        session: SessionState,
        *,
        config: RuntimeConfig,
        fingerprint: BrowserFingerprint,
        request_delay: float,
    ) -> None:
        self.session = session
        self.config = config
        self.fingerprint = fingerprint
        self._request_delay = request_delay
        self._max_retries = config.max_retries
        self._last_request_time = 0.0
        self._request_count = 0
        # Use requests.Session instead of httpx.Client: Reddit's bot
        # detection fingerprints the httpx TLS/HTTP stack and returns
        # a 403 challenge page, while urllib3/requests passes.
        self._http = requests.Session()
        self._http.headers.update(self.default_headers())
        self._http.cookies.update(session.cookies)
        self._http.max_redirects = 10

    def close(self) -> None:
        self._http.close()

    @property
    def client(self) -> requests.Session:
        return self._http

    @property
    def request_count(self) -> int:
        return self._request_count

    def default_headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _rate_limit_delay(self) -> None:
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            jitter = max(0.0, random.gauss(0.3, 0.15))
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            time.sleep(self._request_delay - elapsed + jitter)

    def _merge_response_cookies(self, resp: requests.Response) -> None:
        for name, value in resp.cookies.items():
            if not value:
                continue
            self.client.cookies.set(name, value)
            self.session.cookies[name] = value
        self.session.refresh_capabilities()

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self._rate_limit_delay()
        last_exc: Exception | None = None
        if url.startswith("/"):
            url = BASE_URL + url

        for attempt in range(self._max_retries):
            t0 = time.time()
            try:
                resp = self.client.request(method, url, timeout=self.config.timeout, **kwargs)
                elapsed = time.time() - t0
                self._merge_response_cookies(resp)
                self._request_count += 1
                self._last_request_time = time.time()
                logger.info(
                    "[#%d] %s %s -> %d (%.2fs)",
                    self._request_count,
                    method,
                    url[:80],
                    resp.status_code,
                    elapsed,
                )

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 5))
                    if attempt + 1 >= self._max_retries:
                        raise RateLimitError(retry_after=retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code in (500, 502, 503, 504):
                    wait = (2**attempt) + random.uniform(0, 1)
                    logger.warning("HTTP %d, retrying in %.1fs", resp.status_code, wait)
                    time.sleep(wait)
                    continue

                if resp.status_code == 401:
                    raise SessionExpiredError()
                if resp.status_code == 403:
                    raise ForbiddenError()
                if resp.status_code == 404:
                    raise NotFoundError()

                resp.raise_for_status()

                text = resp.text
                if text.strip().startswith("<"):
                    raise RedditApiError("Received HTML instead of JSON (possible auth redirect)")
                if not text.strip():
                    return {}
                return resp.json()
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                wait = (2**attempt) + random.uniform(0, 1)
                logger.warning("Network error: %s, retrying in %.1fs", exc, wait)
                time.sleep(wait)

        if last_exc:
            raise RedditApiError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc
        raise RedditApiError(f"Request failed after {self._max_retries} retries")


class ReadTransport(BaseTransport):
    """Transport for low-risk listing and detail requests."""

    def default_headers(self) -> dict[str, str]:
        return self.fingerprint.read_headers()


class WriteTransport(BaseTransport):
    """Transport for state-changing authenticated requests."""

    def default_headers(self) -> dict[str, str]:
        return self.fingerprint.write_headers(modhash=self.session.modhash)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        if not self.session.can_write:
            raise RedditApiError("Session is not write-capable yet; run 'rdt status' or 'rdt whoami' to validate")

        headers = dict(kwargs.pop("headers", {}))
        headers.update(self.fingerprint.write_headers(modhash=self.session.modhash))
        kwargs["headers"] = headers

        data = kwargs.get("data")
        if isinstance(data, dict) and self.session.modhash and "uh" not in data:
            kwargs["data"] = {**data, "uh": self.session.modhash}

        return super().request(method, url, **kwargs)
