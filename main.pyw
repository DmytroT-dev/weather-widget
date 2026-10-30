"""Entry point. A .pyw file runs under pythonw, without a console window."""
import logging
from logging.handlers import RotatingFileHandler

import config
from focus.pomodoro import Pomodoro
from news.hackernews import HackerNewsClient
from ui import single_instance, state
from ui.layered import enable_dpi_awareness
from ui.widget import DeskWidget
from weather.geocoding import GeocodingClient
from weather.service import WeatherService


def setup_logging() -> None:
    # pythonw has no console, so without a file every error would vanish. Rotation caps disk usage.
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    if not single_instance.acquire("desk-widget"):
        return  # already running, e.g. started by autostart and then by hand
    setup_logging()
    scale = enable_dpi_awareness()  # before any Tk window exists, otherwise Windows blurs it
    weather = WeatherService(config.METNO_USER_AGENT)
    geocoder = GeocodingClient(config.ANONYMOUS_USER_AGENT)
    news_client = HackerNewsClient(config.ANONYMOUS_USER_AGENT, limit=config.NEWS_LIMIT)
    saved_place = state.load_place(config.STATE_FILE)
    app = DeskWidget(
        scale=scale,
        place=saved_place or config.DEFAULT_PLACE,
        ask_for_place=saved_place is None,  # first start: let the user pick their city
        load_weather=weather.load,
        search_places=geocoder.search,
        load_news=news_client.top_stories,
        pomodoro=Pomodoro(config.FOCUS_S, config.SHORT_BREAK_S, config.LONG_BREAK_S, config.FOCUS_SESSIONS_PER_LONG_BREAK),
        weather_refresh_s=config.REFRESH_INTERVAL_S,
        news_refresh_s=config.NEWS_REFRESH_INTERVAL_S,
        retry_s=config.RETRY_INTERVAL_S,
        state_file=config.STATE_FILE,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
