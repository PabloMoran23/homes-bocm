"""Regresiones del refresco: nunca publicar una descarga fallida como éxito."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from sector_geometry import madrid_licencias_download as download


class LicenseDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.raw = root / "raw"
        self.raw.mkdir()
        self.jsonl = root / "licencias.jsonl"
        self.summary = root / "summary.json"
        self.old_row = {"anio_dataset": 2024, "ndp_edificio": "old"}
        self.jsonl.write_text(json.dumps(self.old_row) + "\n")
        self.summary.write_text(json.dumps({
            "byYear": {"2024": 1},
            "sourceSnapshot": {"resources": {
                "2024": {"sha256": "old-hash", "downloadedThisRun": True}
            }},
        }))
        for name, value in (("OUTPUT_DIR", root), ("RAW_DIR", self.raw),
                            ("JSONL_OUT", self.jsonl), ("SUMMARY_OUT", self.summary)):
            mock = patch.object(download, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def invoke(self, *extra):
        with patch("sys.argv", ["download", "--years", "2025,2026", "--merge-jsonl", *extra]):
            download.main()

    def assert_failure_preserves_snapshot(self):
        before = (self.jsonl.read_bytes(), self.summary.read_bytes())
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertEqual(before, (self.jsonl.read_bytes(), self.summary.read_bytes()))

    def test_http_failure_does_not_publish_stale_cache_as_success(self):
        cached = self.raw / "licencias_urbanisticas_2025.xlsx"
        cached.write_bytes(b"previous-cache")
        with patch.object(download, "_download", side_effect=HTTPError("url", 403, "Forbidden", {}, None)):
            self.assert_failure_preserves_snapshot()
        self.assertEqual(cached.read_bytes(), b"previous-cache")

    def test_partial_download_does_not_publish(self):
        def fetch(url, dest):
            if "300193-2-" in url:
                raise TimeoutError("download timeout")
            dest.write_bytes(b"xlsx")
        with patch.object(download, "_download", side_effect=fetch), patch.object(
            download, "_rows_from_xlsx", return_value=[{"anio_dataset": 2025, "ndp_edificio": "new"}]
        ):
            self.assert_failure_preserves_snapshot()

    def test_empty_or_invalid_resource_preserves_cache(self):
        for result in ([], ValueError("invalid XLSX")):
            with self.subTest(result=result):
                def fetch(url, dest):
                    dest.write_bytes(b"bad download")
                with patch.object(download, "_download", side_effect=fetch), patch.object(
                    download, "_rows_from_xlsx",
                    **({"side_effect": result} if isinstance(result, Exception) else {"return_value": result})
                ):
                    self.assert_failure_preserves_snapshot()

    def test_success_preserves_historical_summary_and_merges_rows(self):
        def fetch(url, dest):
            dest.write_bytes(b"xlsx")
        def parse(path, year):
            return [{"anio_dataset": year, "ndp_edificio": str(year)}]
        with patch.object(download, "_download", side_effect=fetch), patch.object(
            download, "_rows_from_xlsx", side_effect=parse
        ):
            self.invoke()
        summary = json.loads(self.summary.read_text())
        self.assertEqual(summary["totalRows"], 3)
        self.assertEqual(summary["byYear"], {"2024": 1, "2025": 1, "2026": 1})
        resources = summary["sourceSnapshot"]["resources"]
        self.assertFalse(resources["2024"]["downloadedThisRun"])
        self.assertTrue(resources["2026"]["downloadedThisRun"])
        self.assertEqual(resources["2024"]["sha256"], "old-hash")

    def test_unknown_year_fails_before_publishing(self):
        with patch("sys.argv", ["download", "--years", "2099"]):
            with self.assertRaises(SystemExit):
                download.main()


if __name__ == "__main__":
    unittest.main()
