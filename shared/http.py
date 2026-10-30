"""Reading JSON from untrusted HTTP responses: capped size and a total deadline.

`json.load(response)` trusts the server completely: a huge or endlessly trickling body would eat memory
or hang the loading thread forever, because urlopen's timeout applies to each socket read, not to the
whole response.
"""
import json
import time
from typing import Any, Callable

CHUNK_BYTES = 16 * 1024
DEFAULT_DEADLINE_S = 30.0


class ResponseTooLarge(ValueError):
    pass


class ResponseTooSlow(TimeoutError):
    pass


def read_json(response: Any, max_bytes: int, deadline_s: float = DEFAULT_DEADLINE_S,
              clock: Callable[[], float] = time.monotonic) -> Any:
    started = clock()
    chunks: list[bytes] = []
    size = 0
    while chunk := response.read(CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise ResponseTooLarge(f"response is larger than {max_bytes} bytes")
        if clock() - started > deadline_s:
            raise ResponseTooSlow(f"response took longer than {deadline_s} s")
        chunks.append(chunk)
    return json.loads(b"".join(chunks))
