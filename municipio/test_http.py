"""Network-free regression tests for municipal portal timeouts."""

from email.message import Message
from unittest import TestCase
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError, URLError

from municipio.adapters.leon import LeonAyuntamientoAdapter
from municipio.adapters.oviedo import OviedoAyuntamientoAdapter


URL = "https://example.org/urbanismo"


def response(body: bytes = b"ok", charset: str = "utf-8") -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value = result
    result.read.return_value = body
    result.headers = Message()
    result.headers["Content-Type"] = f"text/html; charset={charset}"
    return result


class PortalTimeoutTest(TestCase):
    def setUp(self) -> None:
        self.sleep = self.enterContext(patch("municipio.http.time.sleep"))
        self.urlopen = self.enterContext(patch("municipio.http.urllib.request.urlopen"))
        self.enterContext(patch("municipio.http.logger.warning"))
        self.adapters = [
            LeonAyuntamientoAdapter("leon"),
            OviedoAyuntamientoAdapter("oviedo"),
        ]

    def test_retries_open_and_read_timeouts_preserving_request(self) -> None:
        for adapter in self.adapters:
            with self.subTest(adapter=adapter.slug):
                self.urlopen.reset_mock()
                self.sleep.reset_mock()
                timed_out = response()
                timed_out.read.side_effect = TimeoutError("read timed out")
                self.urlopen.side_effect = [TimeoutError("connect timed out"), timed_out, response()]
                self.assertEqual(adapter._fetch(URL, data=b"search=urbanismo"), "ok")
                self.assertEqual(self.urlopen.call_count, 3)
                requests = [c.args[0] for c in self.urlopen.call_args_list]
                self.assertTrue(all(req is requests[0] for req in requests))
                self.assertEqual(requests[0].data, b"search=urbanismo")
                self.assertEqual(requests[0].get_method(), "POST")
                self.sleep.assert_has_calls([call(2), call(4)])
                timed_out.__exit__.assert_called_once()

    def test_exhausted_timeout_includes_url_and_is_not_silently_skipped(self) -> None:
        for adapter in self.adapters:
            for error in (TimeoutError("read timed out"), URLError(TimeoutError("connect timed out"))):
                with self.subTest(adapter=adapter.slug, error=type(error).__name__):
                    self.urlopen.reset_mock()
                    self.urlopen.side_effect = error
                    with self.assertRaises(TimeoutError) as raised:
                        adapter._fetch(URL)
                    self.assertIn(URL, str(raised.exception))
                    self.assertIn("3 attempts", str(raised.exception))
                    self.assertEqual(self.urlopen.call_count, 3)

    def test_other_url_errors_keep_existing_handling_without_retries(self) -> None:
        for error in (URLError("name resolution failed"), HTTPError(URL, 404, "Not found", {}, None)):
            self.urlopen.reset_mock()
            self.urlopen.side_effect = error
            with self.assertRaises(URLError) as raised:
                self.adapters[0]._fetch(URL)
            self.assertIs(raised.exception, error)
            self.assertEqual(self.urlopen.call_count, 1)

    def test_preserves_portal_encodings(self) -> None:
        self.urlopen.return_value = response("León".encode("iso-8859-1"), "iso-8859-1")
        self.assertEqual(self.adapters[0]._fetch(URL), "León")
        self.assertEqual(self.adapters[1]._fetch(URL, encoding="iso-8859-1"), "León")
