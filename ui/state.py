"""Remembers the window position and the chosen city between runs (one small JSON file)."""
import json
import os
from pathlib import Path
from typing import Any

from weather.geocoding import MAX_TEXT_LENGTH, valid_coordinates
from weather.model import Place


def load_position(path: Path) -> tuple[int, int] | None:
    data = _read(path)
    x, y = data.get("x"), data.get("y")
    # The file is outside our control: accept only plain ints, never feed arbitrary data into Tk.
    if type(x) is int and type(y) is int:
        return x, y
    return None


def save_position(path: Path, x: int, y: int) -> None:
    _update(path, {"x": x, "y": y})


def load_place(path: Path) -> Place | None:
    data = _read(path).get("place")
    if not isinstance(data, dict):
        return None
    name, region, lat, lon = data.get("name"), data.get("region", ""), data.get("lat"), data.get("lon")
    if not isinstance(name, str) or not name or not isinstance(region, str) or not valid_coordinates(lat, lon):
        return None
    return Place(name[:MAX_TEXT_LENGTH], region[:MAX_TEXT_LENGTH], float(lat), float(lon))


def save_place(path: Path, place: Place) -> None:
    _update(path, {"place": {"name": place.name, "region": place.region, "lat": place.lat, "lon": place.lon}})


def visible_position(position: tuple[int, int], size: tuple[int, int],
                     screen: tuple[int, int, int, int]) -> tuple[int, int]:
    """Moves the window back inside `screen` (left, top, width, height), e.g. after a monitor was unplugged."""
    (x, y), (width, height), (left, top, screen_width, screen_height) = position, size, screen
    x = min(max(x, left), left + max(0, screen_width - width))
    y = min(max(y, top), top + max(0, screen_height - height))
    return x, y


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _update(path: Path, values: dict[str, Any]) -> None:
    """Merges `values` into the file, so saving the position does not erase the city and vice versa."""
    data = _read(path)
    data.update(values)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file and swap: a crash mid-write cannot leave a half-written, unreadable file.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # losing the state is not worth crashing the widget
