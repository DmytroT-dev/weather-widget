"""City search via the Open-Meteo geocoding API (free, no key): https://open-meteo.com/en/docs/geocoding-api

Privacy: only the typed city name leaves the machine, and only when the user searches.
"""
import math
import urllib.request
from typing import Any, Callable
from urllib.parse import urlencode

from shared.http import read_json
from weather.model import Place

API_URL = "https://geocoding-api.open-meteo.com/v1/search"
MAX_QUERY_LENGTH = 100
MAX_TEXT_LENGTH = 100
MAX_RESPONSE_BYTES = 256 * 1024


class GeocodingClient:
    def __init__(self, user_agent: str, timeout_s: float = 10,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._opener = opener

    def search(self, query: str, limit: int = 8) -> list[Place]:
        query = " ".join(query.split())[:MAX_QUERY_LENGTH]
        if len(query) < 2:
            return []
        # urlencode escapes '&', '=', '#'...: a city name cannot inject extra query parameters.
        params = urlencode({"name": query, "count": limit, "language": "en", "format": "json"})
        request = urllib.request.Request(f"{API_URL}?{params}", headers={"User-Agent": self._user_agent})
        with self._opener(request, timeout=self._timeout_s) as response:
            data = read_json(response, MAX_RESPONSE_BYTES)
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []  # the API omits "results" when nothing matches
        return [place for place in map(parse_place, results) if place is not None]


def parse_place(item: Any) -> Place | None:
    if not isinstance(item, dict):
        return None
    name, lat, lon = item.get("name"), item.get("latitude"), item.get("longitude")
    if not isinstance(name, str) or not name.strip() or not valid_coordinates(lat, lon):
        return None
    region = ", ".join(item[key].strip() for key in ("admin1", "country")
                       if isinstance(item.get(key), str) and item[key].strip())
    return Place(_clean(name), _clean(region), round(float(lat), 4), round(float(lon), 4))


def valid_coordinates(lat: Any, lon: Any) -> bool:
    return _is_number(lat) and _is_number(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def _is_number(value: Any) -> bool:
    # bool is a subclass of int in Python: True must not become latitude 1.0.
    return type(value) in (int, float) and math.isfinite(value)


def _clean(text: str) -> str:
    return " ".join(text.split())[:MAX_TEXT_LENGTH]
