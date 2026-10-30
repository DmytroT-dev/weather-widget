"""Domain model: what the widget knows about the weather, independent of the API and the UI."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Weather:
    temperature_c: float
    wind_speed_ms: float
    symbol_code: str  # MET Norway code, e.g. "rainshowers_day", "lightsnowandthunder"


@dataclass(frozen=True)
class Place:
    name: str
    region: str  # e.g. "Gelderland, Netherlands"; tells apart cities with the same name
    lat: float
    lon: float

    @property
    def label(self) -> str:
        return f"{self.name}, {self.region}" if self.region else self.name
