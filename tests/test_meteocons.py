import unittest

from tests.metno_symbols import ALL
from weather.meteocons import ASSETS_DIR, FALLBACK_ICON, icon_path, weather_icon, wind_icon


class WeatherIconTest(unittest.TestCase):
    def test_examples(self):
        cases = {
            "clearsky_day": "clear-day",
            "clearsky_night": "clear-night",
            "clearsky_polartwilight": "clear-day",
            "fair_night": "mostly-clear-night",
            "partlycloudy_day": "partly-cloudy-day",
            "cloudy": "cloudy",
            "fog": "fog",
            "lightrain": "drizzle",
            "rain": "rain",
            "heavyrain": "overcast-rain",
            "rainshowers_night": "partly-cloudy-night-rain",
            "lightsnowshowers_day": "partly-cloudy-day-snow",
            "sleet": "sleet",
            "rainandthunder": "thunderstorms-rain",
            "heavysnowshowersandthunder_night": "thunderstorms-night-snow",
            "lightssleetshowersandthunder_day": "thunderstorms-day-sleet",
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(weather_icon(code), expected)

    def test_every_metno_code_has_a_bundled_icon(self):
        for code in ALL:
            with self.subTest(code=code):
                self.assertTrue((ASSETS_DIR / f"{weather_icon(code)}.json").exists())

    def test_unknown_code_falls_back(self):
        self.assertEqual(weather_icon("somethingnew"), FALLBACK_ICON)
        self.assertEqual(icon_path("no-such-icon").name, f"{FALLBACK_ICON}.json")


class WindIconTest(unittest.TestCase):
    def test_beaufort_boundaries(self):
        cases = {0.0: 0, 0.29: 0, 0.3: 1, 3.4: 3, 5.49: 3, 5.5: 4, 32.6: 11, 32.7: 12, 60: 12}
        for speed, force in cases.items():
            with self.subTest(speed=speed):
                self.assertEqual(wind_icon(speed), f"wind-beaufort-{force}")

    def test_every_force_has_a_bundled_icon(self):
        for force in range(13):
            self.assertTrue((ASSETS_DIR / f"wind-beaufort-{force}.json").exists())
