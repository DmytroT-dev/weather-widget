"""Top stories from the official Hacker News API: https://github.com/HackerNews/API"""
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from shared.http import read_json

API_URL = "https://hacker-news.firebaseio.com/v0"
DISCUSSION_URL = "https://news.ycombinator.com/item?id={id}"
MAX_TITLE_LENGTH = 200
MAX_LIST_BYTES = 64 * 1024  # ~500 ids are ~5 KB
MAX_ITEM_BYTES = 256 * 1024
# Invisible characters that make a URL look different from what it is (bidi overrides, zero-width marks).
_DECEPTIVE_CHARS = set("\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                       "\u2066\u2067\u2068\u2069\ufeff")


@dataclass(frozen=True)
class Story:
    id: int
    title: str
    url: str


class HackerNewsClient:
    def __init__(
        self,
        user_agent: str,
        limit: int = 30,
        timeout_s: float = 10,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._user_agent = user_agent
        self._limit = limit
        self._timeout_s = timeout_s
        self._opener = opener

    def top_stories(self) -> list[Story]:
        ids = self._get("topstories.json", MAX_LIST_BYTES)
        if not isinstance(ids, list):
            raise ValueError("topstories is not a list")
        ids = ids[: self._limit]
        # The API has no batch endpoint: one request per item, so fetch them in parallel.
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(self._get_item_or_none, ids))
        return [story for story in map(parse_story, items) if story is not None]

    def _get_item_or_none(self, item_id: Any) -> dict[str, Any] | None:
        try:
            return self._get(f"item/{int(item_id)}.json", MAX_ITEM_BYTES)
        except (OSError, ValueError, TypeError):
            return None  # one broken item must not hide the other 29

    def _get(self, path: str, max_bytes: int) -> Any:
        request = urllib.request.Request(f"{API_URL}/{path}", headers={"User-Agent": self._user_agent})
        with self._opener(request, timeout=self._timeout_s) as response:
            return read_json(response, max_bytes)


def parse_story(item: Any) -> Story | None:
    if not isinstance(item, dict) or item.get("type") != "story" or item.get("dead") or item.get("deleted"):
        return None
    item_id, title = item.get("id"), item.get("title")
    if type(item_id) is not int or not isinstance(title, str) or not title.strip():
        return None
    title = " ".join(title.split())[:MAX_TITLE_LENGTH]  # also strips newlines and control whitespace
    return Story(item_id, title, safe_url(item.get("url")) or DISCUSSION_URL.format(id=item_id))


def safe_url(url: Any) -> str | None:
    """Only http(s) links may reach the browser.

    The URL comes from an untrusted third party. On Windows, opening 'file:', 'javascript:' or a custom
    protocol (e.g. 'ms-msdt:', CVE-2022-30190 "Follina") can execute code instead of showing a web page.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    # urlsplit silently drops tabs/newlines and leading control characters, so it would validate a different
    # string than the one handed to the browser. Reject such input instead of letting the two disagree.
    if any(ord(c) <= 0x20 or ord(c) == 0x7F or c in _DECEPTIVE_CHARS for c in url):
        return None
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return url
