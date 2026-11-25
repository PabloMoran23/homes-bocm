"""Ensure municipal adapters retry an interrupted response before decoding it."""

from email.message import Message
from http.client import IncompleteRead
from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.request import OpenerDirector, Request

from municipio.adapters import load_portal_adapter
from municipio.gis.icv import enable_icv_compression
from municipio.manifest import load_manifest


AFFECTED_MUNICIPALITIES = (
    "alzira",
    "benicarlo-vinaros-benijofar",
    "benidorm",
    "denia",
    "elche-elx",
    "gata-de-gorgos",
    "l-alcora",
    "l-alfas-del-pi",
    "l-olleria",
    "la-llosa-de-ranes",
    "la-pobla-de-farnals",
    "la-puebla-de-cazalla",
    "la-vall-duixo",
    "massamagrell",
    "mislata",
    "onda",
    "ontinyent",
)
URL = "https://terramapas.icv.gva.es/0702_Planeamiento"


class InterruptedAdapterReadTests(TestCase):
    def test_affected_adapters_retry_text_and_structured_downloads(self) -> None:
        text = '{"municipio":"Dénia"}'
        body = text.encode()
        headers = Message()
        headers["Content-Type"] = "application/json; charset=utf-8"
        with (
            patch("municipio.http.time.sleep"),
            patch("municipio.http.logger.warning"),
            patch.object(OpenerDirector, "open") as open_request,
        ):
            for slug in AFFECTED_MUNICIPALITIES:
                adapter = load_portal_adapter(load_manifest(slug))
                for method, expected in (
                    ("_fetch", text),
                    ("_fetch_bytes", body),
                    ("_fetch_json", {"municipio": "Dénia"}),
                ):
                    if not hasattr(adapter, method):
                        continue
                    with self.subTest(slug=slug, method=method):
                        truncated = MagicMock()
                        truncated.__enter__.return_value = truncated
                        truncated.read.side_effect = IncompleteRead(body[:5])
                        complete = MagicMock()
                        complete.__enter__.return_value = complete
                        complete.read.return_value = body
                        complete.headers = headers
                        open_request.reset_mock()
                        open_request.side_effect = [truncated, complete]

                        self.assertEqual(getattr(adapter, method)(URL), expected)
                        self.assertEqual(open_request.call_count, 2)
                        request = open_request.call_args.args[0]
                        self.assertEqual(request.full_url, URL)
                        accept_encoding = None if slug == "la-puebla-de-cazalla" else "gzip"
                        self.assertEqual(request.get_header("Accept-encoding"), accept_encoding)
                        truncated.__exit__.assert_called_once()

    def test_leaves_other_public_portals_unchanged(self) -> None:
        request = Request("https://example.org/planeamiento")
        enable_icv_compression(request)
        self.assertIsNone(request.get_header("Accept-encoding"))
