import json
import ssl
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from municipio.adapters.ferrol import SIOTUGA_QUERY_DOC, TRAMITES_LIST, FerrolAyuntamientoAdapter
from municipio.adapters.medina_de_rioseco import MedinaDeRiosecoAyuntamientoAdapter
from municipio.adapters.vic import (
    PLANEJAMENT_EN_TRAMIT,
    PLANEJAMENT_VIGENT_HTML,
    PLANEJAMENT_VIGENT_RSS,
    RPUC_INVENTORY,
    VicAyuntamientoAdapter,
)
from municipio.idecyl import _idecyl_context


class MunicipalSourceRecoveryTest(TestCase):
    def test_idecyl_chain_keeps_hostname_and_root_verification(self):
        context = _idecyl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertFalse(context.verify_flags & getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0))

    def test_medina_pagination_keeps_previous_inventory_limit(self):
        adapter = MedinaDeRiosecoAyuntamientoAdapter("medina-de-rioseco")

        def fetch(url):
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query["per_page"], ["25"])
            self.assertIn("content", query["_fields"][0].split(","))
            start = 25 * (int(query["page"][0]) - 1)
            return [{"id": start + offset} for offset in range(25)]

        with patch.object(adapter, "_fetch_json", side_effect=fetch):
            rows = adapter._paginate_wp("pages", max_pages=2)
        self.assertEqual([row["id"] for row in rows], list(range(200)))

    def test_ferrol_archive_fallback_does_not_disable_future_live_requests(self):
        adapter = FerrolAyuntamientoAdapter("ferrol", {"request_delay_s": 0})
        with patch("municipio.adapters.ferrol.fetch_text", side_effect=[TimeoutError(), "archive", "live"]) as fetch:
            self.assertEqual(adapter._fetch(TRAMITES_LIST), "archive")
            self.assertEqual(adapter._fetch(TRAMITES_LIST), "live")
        urls = [call.args[0].full_url for call in fetch.call_args_list]
        self.assertEqual(urls[::2], [TRAMITES_LIST, TRAMITES_LIST])
        self.assertEqual(urlsplit(urls[1]).hostname, "web.archive.org")

    def test_ferrol_does_not_send_live_searches_to_an_archive(self):
        adapter = FerrolAyuntamientoAdapter("ferrol", {"request_delay_s": 0, "prefer_wayback": True})
        with patch("municipio.adapters.ferrol.fetch_text", side_effect=TimeoutError) as fetch:
            with self.assertRaises(TimeoutError):
                adapter._fetch(SIOTUGA_QUERY_DOC, data=b"search=data")
        fetch.assert_called_once()
        request = fetch.call_args.args[0]
        self.assertEqual(request.full_url, SIOTUGA_QUERY_DOC)
        self.assertEqual(request.get_method(), "POST")


class VicPlanningRecoveryTest(TestCase):
    def test_current_html_replaces_unavailable_rss_without_changing_source(self):
        adapter = VicAyuntamientoAdapter("vic")
        table = "<tr><td>2026</td><td>Pla especial</td><td>12/11/2026</td><td>123/2026</td></tr>"
        with patch.object(adapter, "_fetch_plain", side_effect=[
            HTTPError(PLANEJAMENT_VIGENT_RSS, 403, "Forbidden", {}, None), table,
        ]):
            rows, error = adapter._read_plone_table(PLANEJAMENT_VIGENT_RSS, PLANEJAMENT_VIGENT_HTML)
        self.assertIsNone(error)
        self.assertEqual(rows[0]["url"], PLANEJAMENT_VIGENT_HTML)

    def test_recovered_rows_keep_official_provenance_and_report_partial_coverage(self):
        adapter = VicAyuntamientoAdapter("vic")

        def fetch(url):
            if not url.startswith(RPUC_INVENTORY):
                raise HTTPError(url, 403, "Forbidden", {}, None)
            return json.dumps({"infoFiltre": "Vic", "totals": 2, "llistat": [
                {"codi": "1", "municipi": "Vic", "tema": "Pla especial del nucli", "instrumentca": "Pla especial"},
                {"codi": "2", "municipi": "Barcelona", "tema": "Pla regional", "instrumentca": "Pla general"},
            ]})

        with TemporaryDirectory() as directory:
            out = Path(directory) / "proyectos.jsonl"
            with patch.object(adapter, "_fetch_plain", side_effect=fetch), patch.object(adapter, "_collect_board", return_value=[{
                "titulo": "Aprovació inicial de modificació del POUM", "categoria": "Urbanisme",
                "url": "https://seuelectronica.vic.cat/preview-document/123", "origen": "tablon",
            }]) as board:
                result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
        board.assert_called_once_with(required=True)
        self.assertEqual(result["status"], "partial")
        self.assertIn(PLANEJAMENT_EN_TRAMIT, result["reason"])
        self.assertIn(PLANEJAMENT_VIGENT_HTML, result["reason"])
        self.assertEqual({row["origen"] for row in rows}, {"registro_rpuc", "tablon"})
        self.assertTrue(all(row["municipio"] == "Vic" for row in rows))
