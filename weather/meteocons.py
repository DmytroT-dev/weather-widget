"""Maps MET Norway symbol codes and wind speed to Meteocons icon names (slugs)."""
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "meteocons" / "fill"
FALLBACK_ICON = "cloudy"

# Upper bounds in m/s for Beaufort forces 0..11; anything above is force 12.
_BEAUFORT_LIMITS = (0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7)

_CLOUD_COVER = {
    "clearsky": "clear",
    "fair": "mostly-clear",
    "partlycloudy": "partly-cloudy",
}


def weather_icon(symbol_code: str) -> str:
    """'rainshowersandthunder_night' -> 'thunderstorms-night-rain'."""
    base, _, variant = symbol_code.partition("_")
    # Only some codes carry a time of day; polar twilight is closer to day than night visually.
    time = {"": "", "night": "night"}.get(variant, "day")
    precipitation = _precipitation(base)

    if "thunder" in base:
        return _join("thunderstorms", time, precipitation)
    if precipitation:
        if "showers" in base:
            return _join("partly-cloudy", time or "day", precipitation)
        if base.startswith("heavy"):
            return _join("overcast", precipitation)
        return precipitation
    if base in _CLOUD_COVER:
        return _join(_CLOUD_COVER[base], time or "day")
    if base in ("cloudy", "fog"):
        return base
    return FALLBACK_ICON


def wind_icon(wind_speed_ms: float) -> str:
    force = next((f for f, limit in enumerate(_BEAUFORT_LIMITS) if wind_speed_ms < limit), 12)
    return f"wind-beaufort-{force}"


def icon_path(slug: str) -> Path:
    path = ASSETS_DIR / f"{slug}.json"
    return path if path.exists() else ASSETS_DIR / f"{FALLBACK_ICON}.json"


def _precipitation(base: str) -> str:
    if "sleet" in base:  # also covers met.no's typo "lightssleetshowersandthunder"
        return "sleet"
    if "snow" in base:
        return "snow"
    if "rain" in base:
        return "drizzle" if base.startswith("light") else "rain"
    return ""


def _join(*parts: str) -> str:
    return "-".join(p for p in parts if p)
