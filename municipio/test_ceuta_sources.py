import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from municipio.adapters.ceuta import PGOU_TOMO3_URL, SIU_PREFIX, SIU_SECTORES, CeutaAyuntamientoAdapter


class CeutaSourceRecoveryTest(TestCase):
    def setUp(self):
        self.adapter = CeutaAyuntamientoAdapter("ceuta")

    def test_verified_siu_sectors_reuse_canonical_id_and_retain_historical_records(self):
        geom = {"type": "Polygon", "coordinates": [[[-5.31, 35.89], [-5.30, 35.89], [-5.30, 35.90], [-5.31, 35.89]]]}
        payload = json.dumps({"type": "FeatureCollection", "features": [{
            "properties": {f"{SIU_PREFIX}ProvINE": "51001", f"{SIU_PREFIX}IdSector": "51001APE_03_01"},
            "geometry": geom,
        }]})

        def fetch(url, **kwargs):
            if url.startswith(SIU_SECTORES):
                return payload
            raise TimeoutError("city publisher unreachable")

        historical = self.adapter._to_proyecto("PGOU 2023 — instrumento APE_03_01", PGOU_TOMO3_URL, "2024-01-08")
        with TemporaryDirectory() as temp:
            output, state = Path(temp) / "proyectos.jsonl", Path(temp) / "proyectos.state.json"
            output.write_text(json.dumps(historical) + '\n{"id":"previous-bocce-notice"}\n')
            with patch.object(self.adapter, "_fetch", side_effect=fetch):
                result = self.adapter.update_proyectos(output, state)
            rows = {row["id"]: row for row in map(json.loads, output.read_text().splitlines())}
            self.assertEqual(result["status"], "partial")
            self.assertIn("bocce", result["reason"])
            self.assertIn("previous-bocce-notice", rows)
            self.assertEqual(len(rows), 2)
            updated = rows[historical["id"]]
            self.assertEqual(updated["fecha"], "2024-01-08")
            self.assertEqual(updated["origen"], "siu_sectores")
            self.assertEqual(updated["geometry_crs"], "EPSG:4326")
            self.assertEqual(updated["geom_geojson"], geom)
            self.assertTrue(updated["geometry_source_url"].startswith(SIU_SECTORES))

    def test_empty_siu_response_does_not_complete_a_failed_planning_refresh(self):
        def fetch(url, **kwargs):
            if url.startswith(SIU_SECTORES):
                return '{"type":"FeatureCollection","features":[]}'
            raise TimeoutError("city publisher unreachable")

        with patch.object(self.adapter, "_fetch", side_effect=fetch):
            with self.assertRaisesRegex(ValueError, "no usable complete Ceuta sector collection"):
                self.adapter._collect_proyectos()

    def test_missing_bulletin_preserves_licence_history_and_reports_partial(self):
        with TemporaryDirectory() as temp:
            output, state = Path(temp) / "licencias.jsonl", Path(temp) / "licencias.state.json"
            output.write_text('{"id":"previous-licence"}\n')
            with patch.object(self.adapter, "_fetch", side_effect=TimeoutError("city publisher unreachable")):
                result = self.adapter.update_licencias(output, state)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["rows"], 1)
            self.assertEqual({item["source"] for item in result["unavailable_sources"]}, {"bocce", "sede_tramites"})
