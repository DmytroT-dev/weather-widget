import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ui.state import load_place, load_position, save_place, save_position
from weather.geocoding import GeocodingClient, parse_place
from weather.model import Place, Weather
from weather.service import WeatherService

KYIV = {"name": "Kyiv", "latitude": 50.45466, "longitude": 30.5238, "admin1": "Kyiv City", "country": "Ukraine"}


class FakeResponse(io.BytesIO):
    def __init__(self, body):
        super().__init__(json.dumps(body).encode())


class ParsePlaceTest(unittest.TestCase):
    def test_regular_result(self):
        self.assertEqual(parse_place(KYIV), Place("Kyiv", "Kyiv City, Ukraine", 50.4547, 30.5238))
        self.assertEqual(parse_place(KYIV).label, "Kyiv, Kyiv City, Ukraine")

    def test_region_is_optional(self):
        self.assertEqual(parse_place({"name": "X", "latitude": 1, "longitude": 2}).region, "")

    def test_rejects_invalid_items(self):
        for item in (None, [], {"name": "X"}, {**KYIV, "name": ""}, {**KYIV, "latitude": "50"},
                     {**KYIV, "latitude": 91}, {**KYIV, "longitude": -181}, {**KYIV, "latitude": True},
                     {**KYIV, "latitude": float("nan")}):
            with self.subTest(item=item):
                self.assertIsNone(parse_place(item))


class GeocodingClientTest(unittest.TestCase):
    def setUp(self):
        self.requests = []

    def client(self, body):
        def opener(request, timeout):
            self.requests.append(request)
            return FakeResponse(body)
        return GeocodingClient("test-agent", opener=opener)

    def test_search_returns_valid_places_only(self):
        places = self.client({"results": [KYIV, {"name": "broken"}]}).search("Kyiv")
        self.assertEqual([p.name for p in places], ["Kyiv"])
        self.assertEqual(self.requests[0].get_header("User-agent"), "test-agent")

    def test_query_cannot_inject_parameters(self):
        self.client({}).search("Kyiv&count=1000#x")
        params = parse_qs(urlsplit(self.requests[0].full_url).query)
        self.assertEqual(params["name"], ["Kyiv&count=1000#x"])
        self.assertEqual(params["count"], ["8"])

    def test_no_results_and_short_queries(self):
        self.assertEqual(self.client({"generationtime_ms": 0.1}).search("Zzzzzz"), [])
        self.assertEqual(self.client({}).search(" k "), [])
        self.assertEqual(len(self.requests), 1)  # the one-letter query never hits the network


class StateTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_place_round_trip_keeps_position(self):
        save_position(self.path, 10, 20)
        save_place(self.path, Place("Kyiv", "Ukraine", 50.45, 30.52))
        save_position(self.path, 30, 40)
        self.assertEqual(load_place(self.path), Place("Kyiv", "Ukraine", 50.45, 30.52))
        self.assertEqual(load_position(self.path), (30, 40))

    def test_tampered_place_is_ignored(self):
        for place in ("Kyiv", {"name": "Kyiv", "lat": "50", "lon": 30}, {"name": "", "lat": 1, "lon": 2},
                      {"name": "Kyiv", "lat": 500, "lon": 30}, {"name": 1, "lat": 1, "lon": 2}):
            with self.subTest(place=place):
                self.path.write_text(json.dumps({"place": place}), encoding="utf-8")
                self.assertIsNone(load_place(self.path))


class WeatherServiceTest(unittest.TestCase):
    def test_one_client_per_location(self):
        created = []

        class FakeClient:
            def __init__(self, lat, lon, user_agent):
                created.append((lat, lon, user_agent))

            def fetch(self):
                return {"properties": {"timeseries": [{"data": {
                    "instant": {"details": {"air_temperature": 1, "wind_speed": 2}},
                    "next_1_hours": {"summary": {"symbol_code": "fog"}}}}]}}

        service = WeatherService("ua", client_factory=FakeClient)
        kyiv, arnhem = Place("Kyiv", "", 50.45, 30.52), Place("Arnhem", "", 51.98, 5.9)
        self.assertEqual(service.load(kyiv), Weather(1.0, 2.0, "fog"))
        service.load(arnhem)
        service.load(kyiv)
        self.assertEqual(created, [(50.45, 30.52, "ua"), (51.98, 5.9, "ua")])
