"""Weather for any place, with one cached MetNoClient per location."""
import threading
from typing import Callable

from weather.client import MetNoClient
from weather.model import Place, Weather
from weather.parser import parse_forecast


class WeatherService:
    def __init__(self, user_agent: str, client_factory: Callable[..., MetNoClient] = MetNoClient) -> None:
        self._user_agent = user_agent
        self._client_factory = client_factory
        self._clients: dict[tuple[float, float], MetNoClient] = {}
        self._lock = threading.Lock()  # loads run on background threads

    def load(self, place: Place) -> Weather:
        # Separate clients keep each location's Expires cache intact when switching cities back and forth.
        key = (place.lat, place.lon)
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = self._clients[key] = self._client_factory(place.lat, place.lon, self._user_agent)
        return parse_forecast(client.fetch())
