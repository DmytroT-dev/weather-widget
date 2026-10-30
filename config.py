"""Widget settings."""
import os
from pathlib import Path

from weather.model import Place

APP = "desk-widget/0.4"

# Shown until the user picks a city (the widget asks on first start). Two decimals (~1 km) are plenty
# for a weather forecast and do not pin down anybody's address.
DEFAULT_PLACE = Place("Arnhem", "Gelderland, Netherlands", 51.98, 5.90)

# MET Norway requires a User-Agent with contact info (email or website), otherwise it may answer 403.
# Set your contact via the WEATHER_WIDGET_CONTACT environment variable.
CONTACT = os.environ.get("WEATHER_WIDGET_CONTACT", "github.com/your-name")
METNO_USER_AGENT = f"{APP} ({CONTACT})"
# Other APIs do not need the contact, so they do not get it: personal data only where it is required.
ANONYMOUS_USER_AGENT = APP

REFRESH_INTERVAL_S = 15 * 60  # the real request rate is also limited by the Expires header
RETRY_INTERVAL_S = 2 * 60

DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "weather-widget"
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "widget.log"

NEWS_LIMIT = 30
NEWS_REFRESH_INTERVAL_S = 30 * 60

FOCUS_S = 25 * 60
SHORT_BREAK_S = 5 * 60
LONG_BREAK_S = 15 * 60
FOCUS_SESSIONS_PER_LONG_BREAK = 4
