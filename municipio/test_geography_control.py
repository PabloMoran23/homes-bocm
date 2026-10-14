from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyproj import Transformer

from municipio.geography_control import normalize_geometry, normalize_record
from municipio.geography_replay import replay_file
from municipio.geocode import _geocode_records

BOUNDARY = {"type": "Polygon", "coordinates": [[[-4, 40], [-3, 40], [-3, 41], [-4, 41], [-4, 40]]]}
CFG = {"municipal_boundary": BOUNDARY}
POLY = {"type": "Polygon", "coordinates": [[[-3.9, 40.1], [-3.8, 40.1], [-3.8, 40.2], [-3.9, 40.2], [-3.9, 40.1]]]}


class GeographyTest(unittest.TestCase):
    def test_declared_projected_crs_and_replay(self):
        x, y = Transformer.from_crs(4326, 25830, always_xy=True).transform(-3.8, 40.2)
        source = {"id": "a", "geom_geojson": {"type": "Point", "coordinates": [x, y]}, "geometry_crs": "EPSG:25830"}
        rec = normalize_record(source, cfg=CFG, municipality="Test")
        self.assertAlmostEqual(rec["lat"], 40.2)
        self.assertAlmostEqual(rec["lng"], -3.8)
        self.assertEqual(rec["geography_original"]["geom_geojson"], source["geom_geojson"])
        self.assertEqual(rec, normalize_record(rec, cfg=CFG, municipality="Test"))
        # A rule/config change reprocesses originals, not already-transformed values.
        rec2 = normalize_record(rec, cfg={**CFG, "axis_order": "yx"}, municipality="Test")
        self.assertEqual(rec2["geography_validation"]["status"], "quarantined")
        recovered = normalize_record(rec2, cfg=CFG, municipality="Test")
        self.assertAlmostEqual(recovered["lng"], -3.8)
        self.assertEqual(rec["geography_validation"]["input_hash"], recovered["geography_validation"]["input_hash"])

    def test_axis_order_explicit_and_unknown_crs(self):
        point = {"type": "Point", "coordinates": [40.2, -3.8]}
        good = normalize_record({"geom_geojson": point, "geometry_crs": "EPSG:4326", "geometry_axis_order": "yx"}, cfg=CFG, municipality="Test")
        self.assertAlmostEqual(good["lat"], 40.2)
        bad = normalize_record({"geom_geojson": point}, cfg=CFG, municipality="Test")
        self.assertNotIn("lat", bad)
        self.assertEqual(bad["geography_validation"]["errors"]["geometry"], "unknown_crs")
        # Apparently plausible coordinates without evidence are not guessed.
        explicit = normalize_record({"lat": 40.2, "lng": -3.8}, cfg=CFG, municipality="Test")
        self.assertEqual(explicit["geography_validation"]["errors"]["coordinates"], "unknown_coordinate_crs")

    def test_nonfinite_range_and_topology(self):
        for point in ([float("nan"), 40], [-3, float("inf")], [-3, 4000000], [40, -3]):
            with self.subTest(point=point):
                rec = normalize_record({"geom_geojson": {"type": "Point", "coordinates": point}, "geometry_crs": "EPSG:4326"}, cfg=CFG, municipality="Test")
                self.assertNotIn("lat", rec)
                json.dumps(rec, allow_nan=False)
        for geometry in ({"type": "FeatureCollection", "features": [{"geometry": POLY}, {"geometry": POLY}]}, {"type": "Polygon", "coordinates": []}, {"type": "unknown", "coordinates": [1, 2]}):
            checked = normalize_record({"geom_geojson": geometry, "geometry_crs": "EPSG:4326"}, cfg=CFG, municipality="Test")
            self.assertIn("geometry", checked["geography_validation"]["errors"])
            self.assertFalse(checked["has_geometry"])
        bowtie = {"type": "Polygon", "coordinates": [[[-3.9, 40.1], [-3.8, 40.2], [-3.9, 40.2], [-3.8, 40.1], [-3.9, 40.1]]]}
        with self.assertRaisesRegex(ValueError, "invalid_topology"):
            normalize_geometry(bowtie, "EPSG:4326")
        unclosed = copy.deepcopy(POLY)
        unclosed["coordinates"][0].pop()
        with self.assertRaisesRegex(ValueError, "unclosed_ring"):
            normalize_geometry(unclosed, "EPSG:4326")

    def test_municipality_scope_requires_all_boundaries_and_evidence(self):
        rec = {"geom_geojson": {"type": "Point", "coordinates": [-2.8, 40.2]}, "geometry_crs": "EPSG:4326"}
        self.assertNotIn("lat", normalize_record(rec, cfg=CFG, municipality="Test"))
        other = {"type": "Polygon", "coordinates": [[[-3, 40], [-2, 40], [-2, 41], [-3, 41], [-3, 40]]]}
        cfg = {"municipal_boundaries": {"Test": BOUNDARY, "Other": other}}
        rec["municipality_scope"] = ["Test", "Other"]
        self.assertNotIn("lat", normalize_record(rec, cfg=cfg, municipality="Test"))
        rec["multimunicipal_evidence"] = "Official instrument explicitly identifies Test and Other"
        self.assertEqual(normalize_record(rec, cfg=cfg, municipality="Test")["lat"], 40.2)
        self.assertNotIn("lat", normalize_record(rec, municipality="Test"))

    def test_two_records_never_leak_element_centroid(self):
        manifest = SimpleNamespace(nombre="Test", slug="test", portal=SimpleNamespace(config={"centroid": [40.7, -3.2]}))
        records = [{"id": "geom", "geom_geojson": POLY, "geometry_crs": "EPSG:4326"}, {"id": "empty"}]
        with patch("municipio.geocode.manifest_geography_config", return_value=CFG), patch("municipio.geocode.official_boundary", return_value=BOUNDARY):
            _geocode_records(records, manifest=manifest, cache={})
        self.assertAlmostEqual(records[0]["lat"], 40.15)
        self.assertLess(abs(records[1]["lat"] - 40.7), 0.002)
        self.assertLess(abs(records[1]["lng"] + 3.2), 0.002)

    def test_replay_dry_run_idempotency_and_changed_source_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proyectos.jsonl"
            original = {"id": "a", "geom_geojson": POLY}
            path.write_text(json.dumps(original) + "\n")
            before = path.read_bytes()
            report = replay_file(path, cfg=CFG, municipality="Test", fetch_boundary=False)
            self.assertEqual(report["quarantined"], 1)
            self.assertEqual(before, path.read_bytes())
            replay_file(path, cfg={**CFG, "source_crs": "EPSG:4326"}, municipality="Test", apply=True, fetch_boundary=False)
            report = replay_file(path, cfg={**CFG, "source_crs": "EPSG:4326"}, municipality="Test", apply=True, fetch_boundary=False)
            self.assertEqual(report["changed"], 0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            rows[0]["geom_geojson"] = {"type": "Point", "coordinates": [-3.6, 40.3]}
            checked = normalize_record(rows[0], cfg={**CFG, "source_crs": "EPSG:4326"}, municipality="Test")
            self.assertEqual(checked["lat"], 40.3)

    def test_actual_alfas_gml_axis_parser_and_arcgis_declaration(self):
        from municipio.adapters.l_alfas_del_pi import _gml_poslist_to_polygon
        from municipio.gis.arcgis import query_mapserver_geojson
        parsed = _gml_poslist_to_polygon("40.1 -3.9 40.1 -3.8 40.2 -3.8 40.1 -3.9")
        self.assertEqual(parsed["coordinates"][0][0], [-3.9, 40.1])
        with patch("municipio.gis.arcgis._http_get_json", return_value={"type": "FeatureCollection", "features": [{"geometry": POLY}]}):
            geom, metadata = query_mapserver_geojson({"mapserver_base": "https://example.test"}, {})
        self.assertEqual(metadata["source_crs"], "EPSG:4326")
        self.assertIn("outSR=4326", metadata["query_url"])
        self.assertEqual(normalize_record({"geom_geojson": geom, "geometry_crs": metadata["source_crs"]}, cfg=CFG, municipality="Test")["geography_validation"]["status"], "valid")

    def test_actual_wfs_adapters_request_declared_crs(self):
        from unittest.mock import MagicMock
        from municipio.adapters.leganes import LeganesAyuntamientoAdapter
        from municipio.adapters.san_sebastian_de_los_reyes import SanSebastianDeLosReyesAyuntamientoAdapter
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"features": [{"geometry": POLY, "properties": {}}]}).encode()
        leganes = LeganesAyuntamientoAdapter("leganes")
        with patch("municipio.adapters.leganes.urllib.request.urlopen", return_value=response) as fetch:
            leganes._fetch_wfs_ambitos()
        self.assertIn("srsName=EPSG%3A4326", fetch.call_args.args[0].full_url)
        ssreyes = SanSebastianDeLosReyesAyuntamientoAdapter("san-sebastian-de-los-reyes", {"request_delay_s": 0})
        with patch("municipio.adapters.san_sebastian_de_los_reyes.urllib.request.urlopen", return_value=response) as fetch:
            geometry = ssreyes._wfs_query("test")
        self.assertIn("srsName=EPSG%3A4326", fetch.call_args.args[0].full_url)
        self.assertEqual(geometry["geometry_crs"], "EPSG:4326")

    def test_direct_save_guards_before_sql_and_clears_stale_coords(self):
        from unittest.mock import MagicMock
        from db import ingest
        connection = MagicMock()
        connection.__enter__.return_value = connection
        source = {"id": "invalid", "lat": 4000000, "lng": 400000, "coordinates_crs": "EPSG:4326", "municipal_boundary": BOUNDARY}
        with patch.object(ingest, "_owned_conn", return_value=connection), patch.object(ingest, "execute_values") as execute:
            ingest.save_proyectos([source])
        sql, tuples = execute.call_args.args[1:3]
        self.assertIsNone(tuples[0][ingest._PROYECTO_UPSERT_COLS.index("lat")])
        self.assertIn("lat = EXCLUDED.lat", sql)
        self.assertIn("geom_geojson = EXCLUDED.geom_geojson", sql)
        with patch.object(ingest, "_owned_conn", return_value=connection), patch.object(ingest, "_next_licencia_ids", return_value={"invalid": 1}), patch.object(ingest, "execute_values") as execute:
            ingest.save_licencias([source])
        sql, tuples = execute.call_args.args[1:3]
        self.assertIsNone(tuples[0][12])
        self.assertIsNone(tuples[0][13])
        self.assertIn("lat = EXCLUDED.lat", sql)

    def test_readonly_database_control_queues_originals_and_recovery(self):
        from unittest.mock import MagicMock
        from municipio.geography_replay import inspect_database
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = [[{"id": "bad", "municipio": "Test", "municipio_slug": "test", "lat": 4000000, "lng": 400000, "geom_geojson": None, "source_original": {}},
                                        {"id": "recover", "municipio": "Test", "municipio_slug": "test", "lat": 4000000, "lng": 400000, "geom_geojson": None,
                                         "source_original": {"lat": 40.2, "lng": -3.8, "coordinates_crs": "EPSG:4326", "municipal_boundary": BOUNDARY}}], [], [], []]
        with patch("municipio.geography_replay.load_manifest", side_effect=FileNotFoundError), patch("municipio.geography_control.official_boundary", return_value=BOUNDARY):
            report = inspect_database(connection)
        connection.set_session.assert_called_once_with(readonly=True)
        self.assertEqual(report["needs_replay"], 2)
        self.assertEqual(report["quarantined"], 1)
        self.assertEqual(report["replay_queue"][1]["action"], "publish_validated_replay")
        self.assertEqual(report["replay_queue"][1]["proposed_geography"]["lat"], 40.2)
        for call in cursor.execute.call_args_list:
            self.assertTrue(call.args[0].startswith("SELECT"))
        source = {"geom_geojson": POLY, "geometry_crs": "EPSG:4326", "_entity_policy": {"status": "x"}, "_semantic_contract": {"status": "y"}}
        checked = normalize_record(source, cfg=CFG, municipality="Test")
        changed = copy.deepcopy(checked)
        changed["_semantic_contract"]["status"] = "z"
        replay = normalize_record(changed, cfg=CFG, municipality="Test")
        self.assertEqual(checked["geography_validation"], replay["geography_validation"])
        self.assertEqual(replay["_entity_policy"], source["_entity_policy"])

    def test_direct_db_mapping_guard(self):
        from db.ingest import _checked_project_row, portal_proyecto_row
        from psycopg2.extras import Json
        invalid = {"id": "direct", "lat": float("inf"), "lng": -3.8, "coordinates_crs": "EPSG:4326", "municipal_boundary": BOUNDARY}
        mapped = portal_proyecto_row(invalid, slug="unknown", nombre="Test")
        self.assertIsNone(mapped["lat"])
        direct = _checked_project_row({**invalid, "municipio": "Test", "geom_geojson": Json({"type": "Point", "coordinates": [1, 5000000]})})
        self.assertIsNone(direct["lat"])
        self.assertFalse(direct["has_geometry"])


if __name__ == "__main__":
    unittest.main()
