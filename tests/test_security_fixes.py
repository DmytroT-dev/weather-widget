import io
import json
import unittest

from news.hackernews import HackerNewsClient, safe_url
from shared.http import ResponseTooLarge, ResponseTooSlow, read_json
from weather.client import MAX_TTL_S, MetNoClient
from weather.parser import parse_forecast


class TrickleResponse:
    """Sends a valid body one byte at a time, like a slowloris server."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self, _size):
        chunk, self._body = self._body[:1], self._body[1:]
        return chunk


class ReadJsonTest(unittest.TestCase):
    def test_reads_normal_body(self):
        self.assertEqual(read_json(io.BytesIO(b'{"a": 1}'), max_bytes=100), {"a": 1})

    def test_rejects_too_large_body(self):
        with self.assertRaises(ResponseTooLarge):
            read_json(io.BytesIO(b"[" + b"1," * 1000 + b"1]"), max_bytes=1000)

    def test_rejects_too_slow_body(self):
        ticks = iter(range(1000))
        with self.assertRaises(ResponseTooSlow):
            read_json(TrickleResponse(b'{"a": 1}'), max_bytes=100, deadline_s=3, clock=lambda: next(ticks))


class SafeUrlParserDifferentialTest(unittest.TestCase):
    def test_rejects_strings_urlsplit_would_silently_rewrite(self):
        for url in ("\x00http://a.com", "ht\ttp://a.com", "http://a.com/\npath", "http://a.com/ x",
                    "https://evil.com‮/moc.elgoog", "https://a​.com", "http://a.com\x7f"):
            with self.subTest(url=repr(url)):
                self.assertIsNone(safe_url(url))

    def test_still_allows_normal_links(self):
        self.assertEqual(safe_url("https://example.com/a?b=c#d"), "https://example.com/a?b=c#d")


class MalformedPayloadTest(unittest.TestCase):
    def forecast(self, next_1_hours):
        data = {"instant": {"details": {"air_temperature": 1, "wind_speed": 2}}, "next_1_hours": next_1_hours}
        return {"properties": {"timeseries": [{"data": data}]}}

    def test_non_string_symbol_code_falls_back(self):
        for block in ({"summary": {"symbol_code": 1}}, {"summary": ["x"]}, ["x"], None):
            with self.subTest(block=block):
                self.assertEqual(parse_forecast(self.forecast(block)).symbol_code, "cloudy")

    def test_topstories_must_be_a_list(self):
        client = HackerNewsClient("ua", opener=lambda request, timeout: io.BytesIO(json.dumps({"x": 1}).encode()))
        with self.assertRaises(ValueError):
            client.top_stories()


class ExpiresCapTest(unittest.TestCase):
    def test_far_future_expires_is_capped(self):
        class Response(io.BytesIO):
            headers = {"Expires": "Fri, 01 Jan 2100 00:00:00 GMT"}

        now = 1_800_000_000.0
        client = MetNoClient(1, 2, "ua", clock=lambda: now, opener=lambda request, timeout: Response(b"{}"))
        client.fetch()
        self.assertEqual(client._expires_at, now + MAX_TTL_S)
