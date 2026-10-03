"""HTTP reads with bounded retries for slow municipal portals."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


def fetch_text(request: urllib.request.Request, *, encoding: str | None = None) -> str:
    """Retry timeouts opening or reading a response, then fail with its URL.

    Callers must only use this for read-only requests (including search POSTs).
    Keep exhausted timeouts distinct from URLError: adapters often skip the
    latter, which would otherwise hide an incomplete refresh.
    """
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                charset = encoding or response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except (TimeoutError, urllib.error.URLError) as exc:
            if not isinstance(exc, TimeoutError) and not isinstance(exc.reason, TimeoutError):
                raise
            if attempt == attempts:
                raise TimeoutError(
                    f"{request.full_url}: timeout after {attempts} attempts "
                    f"(60s per attempt): {exc}"
                ) from exc
            delay = 2 ** attempt
            logger.warning(
                "Timeout fetching %s (attempt %s/%s); retrying in %ss",
                request.full_url, attempt, attempts, delay,
            )
            time.sleep(delay)
