import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

from municipio.adapters.elche_elx import CATALOGO_URL, TABLON_URL, ElcheElxAyuntamientoAdapter


WEB = "https://www.elche.es/urbanismo/tablon-anuncios/"


class ElcheSourcesTest(TestCase):
    def setUp(self):
        self.adapter = ElcheElxAyuntamientoAdapter("elche-elx", {"seed_pages": [WEB]})

    def test_preserves_prior_projects_when_municipal_sources_fail(self):
        with TemporaryDirectory() as temp:
            output, state = Path(temp) / "proyectos.jsonl", Path(temp) / "proyectos.state.json"
            output.write_text('{"id":"previous-board-record"}\n')
            with patch.object(self.adapter, "_fetch", side_effect=[
                TimeoutError("STA connection timeout"), HTTPError(WEB, 502, "Bad Gateway", {}, None),
            ]), patch.object(self.adapter, "_collect_wfs_proyectos", return_value=[{"id": "icv-sector"}]):
                result = self.adapter.update_proyectos(output, state)
            self.assertEqual(result["status"], "partial")
            self.assertEqual([problem["url"] for problem in result["unavailable_sources"]], [TABLON_URL, WEB])
            self.assertEqual(json.loads(state.read_text())["status"], "partial")
            self.assertEqual([json.loads(line)["id"] for line in output.read_text().splitlines()],
                             ["previous-board-record", "icv-sector"])

    def test_licences_report_catalogue_gap_and_reuse_official_web_documents(self):
        with TemporaryDirectory() as temp:
            output = Path(temp) / "licencias.jsonl"
            with patch.object(self.adapter, "_fetch", side_effect=[
                'var dataset_PTS2_TABLON = [];', TimeoutError("STA connection timeout"),
                '<a href="https://www.elche.es/wp-content/uploads/2026/licencia-obra.pdf">Licencia de obra</a>',
            ]):
                result = self.adapter.backfill_licencias(output)
            licences = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(result["status"], "partial")
        self.assertEqual([problem["url"] for problem in result["unavailable_sources"]], [CATALOGO_URL])
        self.assertIn("web_pdf", {row["origen"] for row in licences})

    def test_valid_empty_board_does_not_hide_unrecognizable_responses(self):
        with patch.object(self.adapter, "_fetch", return_value='var dataset_PTS2_TABLON = [];'):
            self.assertEqual(self.adapter._tablon_rows([]), [])
        with patch.object(self.adapter, "_fetch", return_value="<html>Unexpected portal response</html>"):
            with self.assertRaisesRegex(ValueError, "Missing STA board dataset"):
                self.adapter._tablon_rows([])

    def test_planning_refresh_fails_if_the_icv_result_is_an_exception_document(self):
        with patch.object(self.adapter, "_fetch_bytes", return_value=b"<ExceptionReport />"):
            with self.assertRaisesRegex(ValueError, "Invalid ICV WFS"):
                self.adapter._collect_wfs_proyectos()
