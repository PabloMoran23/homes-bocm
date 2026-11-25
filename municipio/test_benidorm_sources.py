import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from municipio.adapters.benidorm import BenidormAyuntamientoAdapter, SEDE_TABLON


class BenidormSourceCoverageTests(TestCase):
    def setUp(self) -> None:
        self.adapter = BenidormAyuntamientoAdapter("benidorm", {"request_delay_s": 0})

    def test_both_updates_preserve_previous_rows_and_report_the_board_gap(self) -> None:
        official_rows = {
            "_crawl_proyectos": [{"id": "municipal-web", "origen": "drupal_urbanismo"}],
            "_collect_wfs_proyectos": [{"id": "regional-wfs", "origen": "icv_wfs"}],
            "_collect_licencias_info": [{"id": "official-forms", "origen": "drupal_tramites"}],
        }
        previous = {"id": "previous-edict", "origen": "sede_tablon", "url": SEDE_TABLON}
        with (
            TemporaryDirectory() as tmp,
            patch.multiple(self.adapter, **{key: lambda rows=rows: rows for key, rows in official_rows.items()}),
            patch.object(self.adapter, "_enrich_geometry"),
            patch.object(self.adapter, "_fetch", side_effect=TimeoutError("verified hosted timeout")) as fetch,
        ):
            for name, expected in (
                ("proyectos", {"municipal-web", "regional-wfs"}),
                ("licencias", {"official-forms"}),
            ):
                with self.subTest(name=name):
                    path = Path(tmp) / f"{name}.jsonl"
                    state = Path(tmp) / f"{name}.state.json"
                    self.adapter._write_jsonl(path, [previous])

                    result = getattr(self.adapter, f"update_{name}")(path, state)
                    records = self.adapter._load_jsonl(path)

                    self.assertEqual({row["id"] for row in records}, expected | {"previous-edict"})
                    self.assertIn(previous, records)
                    self.assertEqual(result["status"], "partial")
                    self.assertEqual(result["reason"], "benidorm_sede_tablon_unavailable")
                    self.assertEqual(result["unavailable_sources"][0]["url"], SEDE_TABLON)
                    self.assertEqual(json.loads(state.read_text())["source_coverage"]["status"], "partial")
            self.assertEqual(fetch.call_count, 2)
            fetch.assert_called_with(SEDE_TABLON, timeout=15, attempts=2)

    def test_mandatory_sources_fail_instead_of_becoming_complete(self) -> None:
        web = self.adapter.seed_pages[0]
        not_found = HTTPError(web, 404, "unavailable", {}, None)
        with patch.object(self.adapter, "_fetch", side_effect=not_found):
            with self.assertRaises(HTTPError):
                self.adapter._crawl_proyectos()
            with self.assertRaises(HTTPError):
                self.adapter._collect_licencias_info()
        with patch.object(self.adapter, "_fetch_bytes", side_effect=URLError("unavailable")):
            with self.assertRaises(URLError):
                self.adapter._collect_wfs_proyectos()
        self.assertIsNone(self.adapter._wfs_cache)

    def test_custom_board_failure_is_not_an_allowed_degradation(self) -> None:
        self.adapter.sede_tablon = "https://example.org/another-board"
        with patch.object(self.adapter, "_fetch", side_effect=TimeoutError("unavailable")):
            with self.assertRaises(TimeoutError):
                self.adapter._collect_tablon()

    def test_accessible_board_keeps_current_notices(self) -> None:
        panel = "<tr><td>Modificación del Plan General de Benidorm</td><td>25/11/2026</td></tr>"
        with patch.object(self.adapter, "_fetch", return_value=panel):
            rows, error = self.adapter._collect_tablon()
        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origen"], "sede_tablon")
        self.assertEqual(rows[0]["url"], SEDE_TABLON)
