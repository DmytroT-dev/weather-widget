import io
import json
import unittest

from news.hackernews import HackerNewsClient, Story, parse_story, safe_url


def story(id=1, title="Show HN: A thing", url="https://example.com/a", **extra):
    return {"id": id, "type": "story", "title": title, "url": url, **extra}


class SafeUrlTest(unittest.TestCase):
    def test_allows_http_and_https(self):
        self.assertEqual(safe_url("https://example.com/x?y=1"), "https://example.com/x?y=1")
        self.assertEqual(safe_url(" HTTP://example.com "), "HTTP://example.com")

    def test_rejects_dangerous_or_broken_urls(self):
        for url in ("javascript:alert(1)", "file:///C:/Windows/System32/calc.exe", "ms-msdt:/id PCWDiagnostic",
                    "https://", "//example.com", "", None, 42):
            with self.subTest(url=url):
                self.assertIsNone(safe_url(url))


class ParseStoryTest(unittest.TestCase):
    def test_regular_story(self):
        self.assertEqual(parse_story(story()), Story(1, "Show HN: A thing", "https://example.com/a"))

    def test_story_without_url_links_to_discussion(self):
        self.assertEqual(parse_story(story(url=None)).url, "https://news.ycombinator.com/item?id=1")

    def test_dangerous_url_falls_back_to_discussion(self):
        self.assertEqual(parse_story(story(url="javascript:alert(1)")).url, "https://news.ycombinator.com/item?id=1")

    def test_title_is_normalised_and_capped(self):
        self.assertEqual(parse_story(story(title="  Two\nlines\t here ")).title, "Two lines here")
        self.assertEqual(len(parse_story(story(title="x" * 500)).title), 200)

    def test_skips_non_stories(self):
        for item in (None, [], {}, story(type="job"), story(dead=True), story(deleted=True),
                     story(title=""), story(title=None), story(id="1")):
            with self.subTest(item=item):
                self.assertIsNone(parse_story(item))


class FakeResponse(io.BytesIO):
    def __init__(self, body):
        super().__init__(json.dumps(body).encode())


class HackerNewsClientTest(unittest.TestCase):
    def test_fetches_top_stories_in_order_and_skips_failures(self):
        pages = {
            "topstories.json": [3, 1, 2, 4],
            "item/1.json": story(id=1, title="one"),
            "item/2.json": story(id=2, type="comment"),
            "item/3.json": story(id=3, title="three"),
        }
        requests = []

        def opener(request, timeout):
            requests.append(request)
            path = request.full_url.split("/v0/", 1)[1]
            if path not in pages:
                raise OSError("network down")
            return FakeResponse(pages[path])

        stories = HackerNewsClient("test-agent", limit=4, opener=opener).top_stories()

        self.assertEqual([s.title for s in stories], ["three", "one"])
        self.assertTrue(all(r.get_header("User-agent") == "test-agent" for r in requests))

    def test_respects_limit(self):
        def opener(request, timeout):
            if request.full_url.endswith("topstories.json"):
                return FakeResponse(list(range(1, 100)))
            return FakeResponse(story(id=int(request.full_url.rsplit("/", 1)[1].split(".")[0])))

        self.assertEqual(len(HackerNewsClient("ua", limit=5, opener=opener).top_stories()), 5)
