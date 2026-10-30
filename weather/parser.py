"""Parses the locationforecast/2.0 JSON response into the Weather domain model."""
from typing import Any

from weather.model import Weather


class ForecastFormatError(ValueError):
    """The API response does not look like what we expect."""


def parse_forecast(data: dict[str, Any]) -> Weather:
    try:
        now = data["properties"]["timeseries"][0]["data"]
        details = now["instant"]["details"]
        temperature = float(details["air_temperature"])
        wind = float(details["wind_speed"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ForecastFormatError(f"unexpected forecast format: {e!r}") from e

    return Weather(temperature, wind, _symbol_code(now))


def _symbol_code(now: dict[str, Any]) -> str:
    # next_1_hours disappears at the end of the forecast horizon, so take the nearest available period.
    for period in ("next_1_hours", "next_6_hours", "next_12_hours"):
        block = now.get(period)
        summary = block.get("summary") if isinstance(block, dict) else None
        code = summary.get("symbol_code") if isinstance(summary, dict) else None
        if isinstance(code, str) and code:  # untrusted JSON: a number here would crash the icon mapping
            return code
    return "cloudy"
