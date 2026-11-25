"""HTTP reads with bounded retries for municipal portals."""

from __future__ import annotations

import gzip
import logging
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from email.message import Message
from http.client import HTTPResponse, IncompleteRead


logger = logging.getLogger(__name__)
_TRANSIENT_READ_ERRORS = (TimeoutError, IncompleteRead, ConnectionError, EOFError, gzip.BadGzipFile, zlib.error)


class PortalReadError(RuntimeError):
    """A portal could not deliver a complete response within the retry budget."""


def read_response(
    request: urllib.request.Request,
    *,
    opener: Callable[..., HTTPResponse] | None = None,
    timeout: float = 60,
    attempts: int = 3,
) -> tuple[bytes, Message]:
    """Retry transient failures for a read-only request, including search POSTs."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    open_request = opener if opener is not None else urllib.request.urlopen
    for attempt in range(1, attempts + 1):
        try:
            with open_request(request, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding", "").strip().lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw, response.headers
        except (*_TRANSIENT_READ_ERRORS, urllib.error.URLError) as exc:
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            if not isinstance(reason, _TRANSIENT_READ_ERRORS):
                raise
            is_timeout = isinstance(reason, TimeoutError)
            failure = "timeout" if is_timeout else type(reason).__name__
            if attempt == attempts:
                # Several collectors treat URLError as a missing optional page.
                # A failed transfer must stay distinguishable from that case.
                error = TimeoutError if is_timeout else PortalReadError
                raise error(
                    f"{request.full_url}: {failure} after {attempts} attempts "
                    f"({timeout:g}s per attempt): {exc}"
                ) from exc
            delay = 2 ** attempt
            logger.warning(
                "%s fetching %s (attempt %s/%s); retrying in %ss",
                failure,
                request.full_url, attempt, attempts, delay,
            )
            time.sleep(delay)
    raise AssertionError("request loop exhausted without a result")


def fetch_text(
    request: urllib.request.Request,
    *,
    encoding: str | None = None,
    opener: Callable[..., HTTPResponse] | None = None,
    timeout: float = 60,
    attempts: int = 3,
) -> str:
    raw, headers = read_response(request, opener=opener, timeout=timeout, attempts=attempts)
    charset = encoding or headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")
