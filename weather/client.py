"""MET Norway (api.met.no) HTTP client with caching based on Expires / Last-Modified.

API rules: https://api.met.no/doc/TermsOfService
- a meaningful User-Agent with contact info is mandatory, otherwise 403;
- do not request more often than the Expires header allows;
- If-Modified-Since -> 304 when the data has not changed;
- coordinates with at most 4 decimals.
"""
import time
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import HTTPError

from shared.http import read_json

API_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
FALLBACK_TTL_S = 30 * 60
MAX_TTL_S = 6 * 60 * 60  # a bogus far-future Expires must not freeze the forecast
MAX_RESPONSE_BYTES = 1024 * 1024  # a real compact forecast is ~40 KB


class MetNoClient:
    def __init__(
        self,
        lat: float,
        lon: float,
        user_agent: str,
        timeout_s: float = 10,
        clock: Callable[[], float] = time.time,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._url = f"{API_URL}?lat={round(lat, 4)}&lon={round(lon, 4)}"
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._clock = clock
        self._opener = opener
        self._cached: dict[str, Any] | None = None
        self._expires_at = 0.0
        self._last_modified: str | None = None

    def fetch(self) -> dict[str, Any]:
        if self._cached is not None and self._clock() < self._expires_at:
            return self._cached

        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        if self._last_modified and self._cached is not None:
            headers["If-Modified-Since"] = self._last_modified
        request = urllib.request.Request(self._url, headers=headers)

        try:
            with self._opener(request, timeout=self._timeout_s) as response:
                self._cached = read_json(response, MAX_RESPONSE_BYTES)
                self._remember(response.headers)
        except HTTPError as e:
            if e.code == 304 and self._cached is not None:
                self._remember(e.headers)
            else:
                raise
        return self._cached

    def _remember(self, headers: Any) -> None:
        self._last_modified = headers.get("Last-Modified") or self._last_modified
        self._expires_at = self._parse_expires(headers.get("Expires"))

    def _parse_expires(self, value: str | None) -> float:
        now = self._clock()
        if value:
            try:
                return min(parsedate_to_datetime(value).timestamp(), now + MAX_TTL_S)
            except (TypeError, ValueError):
                pass
        return now + FALLBACK_TTL_S
