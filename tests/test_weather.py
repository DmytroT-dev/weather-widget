import io
import json
import unittest
from email.message import Message
from urllib.error import HTTPError

from weather.client import FALLBACK_TTL_S, MetNoClient
from weather.parser import ForecastFormatError, parse_forecast


def forecast(temp=12.3, wind=4.6, next_1h="rainandthunder", next_6h=None):
    data = {"instant": {"details": {"air_temperature": temp, "wind_speed": wind}}}
    if next_1h:
        data["next_1_hours"] = {"summary": {"symbol_code": next_1h}}
    if next_6h:
        data["next_6_hours"] = {"summary": {"symbol_code": next_6h}}
    return {"properties": {"timeseries": [{"time": "2026-10-30T12:00:00Z", "data": data}]}}


class ParseForecastTest(unittest.TestCase):
    def test_reads_current_values(self):
        weather = parse_forecast(forecast())
        self.assertEqual(weather.temperature_c, 12.3)
        self.assertEqual(weather.wind_speed_ms, 4.6)
        self.assertEqual(weather.symbol_code, "rainandthunder")

    def test_falls_back_to_six_hour_symbol(self):
        weather = parse_forecast(forecast(next_1h=None, next_6h="snow"))
        self.assertEqual(weather.symbol_code, "snow")

    def test_broken_payload_raises_domain_error(self):
        for payload in ({}, {"properties": {"timeseries": []}}, forecast(temp="warm")):
            with self.subTest(payload=payload):
                with self.assertRaises(ForecastFormatError):
                    parse_forecast(payload)


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(json.dumps(body).encode())
        self.headers = headers


def headers(**values):
    msg = Message()
    for key, value in values.items():
        msg[key.replace("_", "-")] = value
    return msg


class FakeClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class MetNoClientTest(unittest.TestCase):
    EXPIRES = "Fri, 30 Oct 2026 12:30:00 GMT"  # = 1793363400
    EXPIRES_TS = 1793363400

    def setUp(self):
        self.requests = []
        self.responses = []
        self.clock = FakeClock(self.EXPIRES_TS - 600)

    def opener(self, request, timeout):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def client(self):
        return MetNoClient(51.98512345, 5.89871234, "test-agent/1.0 (me@example.com)", clock=self.clock, opener=self.opener)

    def test_sends_user_agent_and_rounds_coordinates(self):
        self.responses.append(FakeResponse({"ok": 1}, headers(Expires=self.EXPIRES)))
        self.client().fetch()
        request = self.requests[0]
        self.assertEqual(request.get_header("User-agent"), "test-agent/1.0 (me@example.com)")
        self.assertIn("lat=51.9851&lon=5.8987", request.full_url)

    def test_uses_cache_until_expires(self):
        self.responses.append(FakeResponse({"ok": 1}, headers(Expires=self.EXPIRES)))
        client = self.client()
        client.fetch()
        client.fetch()
        self.assertEqual(len(self.requests), 1)

    def test_revalidates_with_if_modified_since_and_handles_304(self):
        last_modified = "Fri, 30 Oct 2026 12:00:00 GMT"
        self.responses.append(FakeResponse({"ok": 1}, headers(Expires=self.EXPIRES, Last_Modified=last_modified)))
        not_modified = HTTPError("url", 304, "Not Modified", headers(Expires="Fri, 30 Oct 2026 13:00:00 GMT"), None)
        self.responses.append(not_modified)
        client = self.client()
        client.fetch()

        self.clock.now = self.EXPIRES_TS + 1
        self.assertEqual(client.fetch(), {"ok": 1})
        self.assertEqual(self.requests[1].get_header("If-modified-since"), last_modified)

    def test_missing_expires_uses_fallback_ttl(self):
        self.responses.append(FakeResponse({"ok": 1}, headers()))
        client = self.client()
        client.fetch()
        self.clock.now += FALLBACK_TTL_S - 1
        client.fetch()
        self.assertEqual(len(self.requests), 1)

    def test_http_errors_propagate(self):
        self.responses.append(HTTPError("url", 403, "Forbidden", headers(), None))
        with self.assertRaises(HTTPError):
            self.client().fetch()


if __name__ == "__main__":
    unittest.main()
