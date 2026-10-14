import json
import unittest
import tempfile
from unittest.mock import patch
from datetime import date
from pathlib import Path
from license_dates import parse_date, license_temporal


class LicenseDateTests(unittest.TestCase):
    def test_shared_contract(self):
        cases = json.loads((Path(__file__).parents[1] / "tests/license-date-cases.json").read_text())
        for row in cases:
            with self.subTest(raw=row["raw"]):
                actual = parse_date(row["raw"], as_of=date(2026, 10, 14), meaning=row.get("meaning", "observed"))
                for key in ("value", "precision", "reason"):
                    self.assertEqual(actual[key], row.get(key))

    def test_invalid_primary_does_not_fallback(self):
        actual = license_temporal({"fecha_concesion": "2027-01-01", "fecha_alta": "2025-01-01", "anio_dataset": 2025}, as_of=date(2026, 10, 14))
        self.assertIsNone(actual["year"])
        self.assertIsNone(actual["month"])
        self.assertEqual(actual["quarantine"][0]["reason"], "future_observed_date")

    def test_replay_originals(self):
        original = license_temporal({"fecha_concesion": "2027-01-01"}, as_of=date(2026, 10, 14))
        recovered = license_temporal({"raw_json": {"temporal": original}}, as_of=date(2027, 1, 2))
        self.assertEqual(recovered["month"], "2027-01")

    def test_export_rebuild_and_quarantine(self):
        from export_web_data_from_supabase import export_licencias, _licencia_year
        class Cursor:
            def execute(self, _sql): pass
            def fetchall(self): return [{"fuente": "madrid-opendata", **r} for r in self.rows]
        cursor = Cursor()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            cursor.rows = [{"id": 1, "fecha_concesion": "14/10/2025"}, {"id": 2, "anio_dataset": 8202}, {"id": 3, "fecha_concesion": "2025"}]
            export_licencias(out, cursor, 2022)
            self.assertEqual(len(json.loads((out / "madrid-licencias-2025.json").read_text())), 2)
            self.assertFalse((out / "madrid-licencias-8202.json").exists())
            self.assertEqual(len(json.loads((out / "madrid-license-temporal-quarantine.json").read_text())), 1)
            cursor.rows = [{"id": 1, "fecha_concesion": "2024-02-29"}]
            export_licencias(out, cursor, 2022)
            self.assertFalse((out / "madrid-licencias-2025.json").exists())
            export_licencias(out, cursor, 2022)
            self.assertEqual(len(json.loads((out / "madrid-licencias-2024.json").read_text())), 1)
            self.assertIsNone(_licencia_year({"anio_dataset": 8202}))
            self.assertEqual(_licencia_year({"fecha_concesion": "29/02/2024"}), 2024)

    def test_ingestion_replaces_invalid_dates_preserves_evidence(self):
        import ingest
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *_): pass
        class Conn:
            def cursor(self): return Cursor()
        with patch.object(ingest, "ensure_schema"), patch.object(ingest, "_classify_saved"), patch.object(ingest, "_next_licencia_ids", return_value={"same-key": 42}), patch.object(ingest, "execute_values") as execute:
            for value, expected in [("2024-02-29", "2024-02-29"), ("29/02/2023", None), ("2025-02", "2025-02")]:
                ingest.save_licencias([{"id": "same-key", "fecha_concesion": value}], conn=Conn())
                sql, rows = execute.call_args.args[1:3]
                self.assertEqual(rows[0][0], 42)
                self.assertEqual(rows[0][5], expected)
                self.assertEqual(rows[0][14].adapted["temporal"]["fields"]["fecha_concesion"]["raw"], value)
                self.assertIn("fecha_concesion = EXCLUDED.fecha_concesion", sql)

    def test_madrid_collector_normalizes_each_snapshot(self):
        import sync_madrid_public_to_supabase as sync
        source = [{"ndp_edificio": "100", "anio_dataset": 2025, "fecha_concesin": "29/02/2024"}, {"ndp_edificio": "101", "anio_dataset": 8202}]
        with patch.object(sync, "iter_licencias_rows", return_value=iter(source)):
            _, rows, stats = sync.collect_licencias()
        values = list(rows.values())
        self.assertEqual(values[0][2:5], (2024, None, "2024-02-29"))
        self.assertIsNone(values[1][2])
        self.assertEqual(stats["temporal_quarantine"], 1)
        self.assertEqual(values[0][13].adapted["fecha_concesin"], "29/02/2024")


if __name__ == "__main__":
    unittest.main()
