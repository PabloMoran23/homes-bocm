"""Real PostGIS regression. Uses only an explicitly named disposable local DB.

H03_TEST_DB_URL=postgresql://.../h03_geography_tests python -m unittest db.test_geography_postgres -v
Optional H03_SEMANTICS_ROOT points to the checkout of PR #857 for its real replay.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import unittest

import psycopg2
from psycopg2.extras import Json

MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/20261014185200_geographic_coordinate_guard.sql"
VALID_POINT = {"type": "Point", "coordinates": [-3.8, 40.2]}
VALID_POLYGON = {"type": "Polygon", "coordinates": [[[-3.9, 40.1], [-3.8, 40.1], [-3.8, 40.2], [-3.9, 40.1]]]}
INVALID_POLYGON = {"type": "Polygon", "coordinates": [[[-3.9, 40.1], [-3.8, 40.2], [-3.9, 40.2], [-3.8, 40.1], [-3.9, 40.1]]]}


def semantics_replay(root: Path):
    """Load actual H02 functions without editing or polluting either checkout."""
    original_path = sys.path[:]
    modules = {name: sys.modules.get(name) for name in ("ingest", "project_semantics")}
    municipal_modules = {name: module for name, module in sys.modules.items() if name == "municipio" or name.startswith("municipio.")}
    try:
        sys.path[:0] = [str(root / "db"), str(root)]
        sys.modules.pop("project_semantics", None)
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        ingest = load("_h03_semantic_ingest", root / "db/ingest.py")
        sys.modules["ingest"] = ingest
        return load("_h03_semantic_replay", root / "db/reprocess_project_semantics.py").replay
    finally:
        sys.path[:] = original_path
        for name in list(sys.modules):
            if name == "municipio" or name.startswith("municipio."):
                sys.modules.pop(name)
        sys.modules.update(municipal_modules)
        for name, module in modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@unittest.skipUnless(os.getenv("H03_TEST_DB_URL"), "requires disposable local PostgreSQL/PostGIS")
class GeographyPostgresTest(unittest.TestCase):
    def setUp(self):
        dsn = os.environ["H03_TEST_DB_URL"]
        params = psycopg2.extensions.parse_dsn(dsn)
        if not params.get("dbname", "").startswith("h03_") or params.get("host", "") not in ("localhost", "127.0.0.1", "::1") and not params.get("host", "").startswith("/tmp/h03-"):
            raise RuntimeError("Tests only allow explicitly named h03_* databases on local disposable servers")
        self.conn = psycopg2.connect(dsn)
        with self.conn.cursor() as cur:
            cur.execute("SELECT public.postgis_full_version()")
            self.version = cur.fetchone()[0]
            cur.execute("DROP SCHEMA IF EXISTS homes CASCADE; CREATE SCHEMA homes")
            cur.execute("""CREATE TABLE homes.proyecto (
              id text PRIMARY KEY, municipio text, municipio_slug text, fuente text,
              lat double precision, lng double precision, centroid_lat double precision, centroid_lng double precision,
              bbox_min_lng double precision, bbox_min_lat double precision, bbox_max_lng double precision, bbox_max_lat double precision,
              geom_geojson jsonb, has_geometry boolean DEFAULT false, coord_source text, raw_features_json jsonb,
              fase text, fase_normalizada text, fecha_aprob date, bocm_pub_date date,
              resumen_contenido text, bocm_resumen text, updated_at timestamptz);
              CREATE TABLE homes.licencia (id text PRIMARY KEY, licencia_key text GENERATED ALWAYS AS (id) STORED, lat double precision, lng double precision, raw_json jsonb, municipio_slug text DEFAULT 'leganes')""")
            source = {"titulo": "Plan Norte", "tipo": "Plan parcial", "fase": "Información pública", "fecha": "2026-10-14", "_entity_policy": {"status": "retained"}}
            cur.execute("""INSERT INTO homes.proyecto(id,municipio_slug,fuente,lat,lng,centroid_lat,centroid_lng,
                        geom_geojson,has_geometry,coord_source,raw_features_json)
                        VALUES ('legacy:1','leganes','ayuntamiento',4000000,400000,4000000,400000,%s,true,'legacy',%s)""",
                        (Json({"type": "Point", "coordinates": [400000, 4000000]}), Json(source)))
            cur.execute("""INSERT INTO homes.proyecto(id,fuente,lat,lng,geom_geojson,has_geometry,raw_features_json)
                        VALUES ('valid:1','sigma',40.2,-3.8,%s,true,'{"original":"preserved"}')""", (Json(VALID_POINT),))
            cur.execute("INSERT INTO homes.licencia(id,lat,lng,raw_json) VALUES ('legacy:lic', 'NaN', 400000, '{" + '"origen":"raw"' + "}')")
        self.conn.commit()

    def tearDown(self):
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("DROP SCHEMA homes CASCADE")
        self.conn.commit()
        self.conn.close()

    def migrate(self, sql=None):
        with self.conn.cursor() as cur:
            cur.execute(sql or MIGRATION.read_text())
        self.conn.commit()

    def test_valid_geometry_is_accepted_invalid_rejected(self):
        self.migrate()
        with self.conn.cursor() as cur:
            for geometry in (VALID_POINT, VALID_POLYGON, {"type": "Point", "coordinates": [-3.8, 40.2, 50]}, {"type": "LineString", "coordinates": [[-3.8, 40.2], [-3.7, 40.3]]}):
                cur.execute("SELECT homes.valid_wgs84_geometry(%s)", (Json(geometry),))
                self.assertTrue(cur.fetchone()[0])
            for geometry in ({"type": "Point", "coordinates": [-3.8, 40.2, "NaN"]}, {"type": "Point", "coordinates": [-3.8, 40.2, "Infinity"]},
                             {"type": "Point", "coordinates": ["-3.8", "40.2"]}, INVALID_POLYGON, {"type": "Point", "coordinates": [400000, 4000000]}, {},
                             {"type": "Polygon", "coordinates": []}, {"type": "Point", "coordinates": [40.2, -3.8]},
                             {"type": "Point", "coordinates": [-3.8, 40.2], "crs": {"type": "name", "properties": {"name": "EPSG:25830"}}}):
                cur.execute("SELECT homes.valid_wgs84_geometry(%s)", (Json(geometry),))
                self.assertFalse(cur.fetchone()[0], geometry)
            cur.execute("SELECT homes.valid_wgs84_geometry(NULL)")
            self.assertTrue(cur.fetchone()[0])
            cur.execute("SELECT bool_and(convalidated) FROM pg_constraint WHERE connamespace='homes'::regnamespace AND contype='c'")
            self.assertTrue(cur.fetchone()[0])

    def test_quarantine_preserves_originals_and_metadata_updates_work(self):
        self.migrate()
        with self.conn.cursor() as cur:
            cur.execute("SELECT lat,lng,geom_geojson,has_geometry,raw_features_json FROM homes.proyecto WHERE id='legacy:1'")
            lat, lng, geom, located, raw = cur.fetchone()
            self.assertEqual((lat, lng, geom, located), (None, None, None, False))
            self.assertEqual(raw["_geography_quarantine"]["original"]["lat"], 4000000)
            self.assertIsNone(raw["_geography_quarantine"]["source_crs"])
            self.assertEqual(raw["_entity_policy"], {"status": "retained"})
            # H01 policy UPDATE raw, followed by H02 UPDATE phase/raw, both succeed.
            cur.execute("UPDATE homes.proyecto SET raw_features_json=jsonb_set(raw_features_json, '{_entity_policy}', %s) WHERE id='legacy:1'", (Json({"status": "classified"}),))
            cur.execute("UPDATE homes.proyecto SET fase='Información pública', fase_normalizada='informacion_publica', raw_features_json=jsonb_set(raw_features_json, '{_semantic_contract}', %s) WHERE id='legacy:1'", (Json({"status": "factual"}),))
            cur.execute("UPDATE homes.licencia SET raw_json=jsonb_set(raw_json, '{_entity_policy}', %s) WHERE id='legacy:lic'", (Json({"status": "classified"}),))
            cur.execute("SELECT raw_json FROM homes.licencia WHERE id='legacy:lic'")
            licence_raw = cur.fetchone()[0]
            self.assertEqual(licence_raw["_geography_quarantine"]["original"]["lat"], "NaN")
            self.assertEqual(licence_raw["origen"], "raw")
            cur.execute("SELECT lat,lng,geom_geojson,raw_features_json FROM homes.proyecto WHERE id='valid:1'")
            self.assertEqual(cur.fetchone(), (40.2, -3.8, VALID_POINT, {"original": "preserved"}))
        self.conn.commit()
        self.migrate()
        with self.conn.cursor() as cur:
            cur.execute("SELECT raw_features_json FROM homes.proyecto WHERE id='legacy:1'")
            replayed = cur.fetchone()[0]
            self.assertEqual(replayed["_geography_quarantine"], raw["_geography_quarantine"])
            self.assertEqual(replayed["_semantic_contract"], {"status": "factual"})

    def test_migrated_legacy_stays_in_readonly_replay_queue(self):
        from unittest.mock import patch
        from municipio.geography_replay import inspect_database
        self.migrate()
        with psycopg2.connect(os.environ["H03_TEST_DB_URL"]) as readonly:
            with patch("municipio.geography_control.official_boundary", return_value=None):
                report = inspect_database(readonly)
        queued = {r["id"]: r for r in report["replay_queue"]}
        self.assertEqual(queued["legacy:1"]["original"]["lat"], 4000000)
        self.assertEqual(queued["legacy:1"]["action"], "recover_declared_source_and_replay")
        self.assertEqual(queued["legacy:lic"]["original"]["lat"], "NaN")

    def test_new_invalid_insert_and_geographic_update_are_blocked(self):
        self.migrate()
        statements = [
            ("INSERT INTO homes.proyecto(id,lat,lng) VALUES ('new:1',4000000,400000)", None),
            ("INSERT INTO homes.proyecto(id,geom_geojson,has_geometry) VALUES ('new:geom',%s,true)", (Json(INVALID_POLYGON),)),
            ("UPDATE homes.proyecto SET geom_geojson=%s,has_geometry=true WHERE id='legacy:1'", (Json(INVALID_POLYGON),)),
            ("UPDATE homes.proyecto SET lat='Infinity',lng=-3.8 WHERE id='legacy:1'", None),
            ("UPDATE homes.proyecto SET bbox_min_lng=500000,bbox_min_lat=40,bbox_max_lng=600000,bbox_max_lat=41 WHERE id='valid:1'", None),
            ("INSERT INTO homes.licencia(id,lat,lng) VALUES ('new:lic',40.2,NULL)", None),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    with self.conn.cursor() as cur:
                        cur.execute(sql, params)
                self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO homes.proyecto(id,lat,lng,geom_geojson,has_geometry) VALUES ('new:valid',40.2,-3.8,%s,true)", (Json(VALID_POINT),))
        self.conn.commit()

    def test_undefined_function_is_not_swallowed_and_migration_rolls_back(self):
        broken = MIGRATION.read_text().replace("public.Box3D(geom)", "public.h03_nonexistent_box3d(geom)")
        with self.assertRaises(psycopg2.errors.UndefinedFunction):
            self.migrate(broken)
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("SELECT lat,lng,raw_features_json ? '_geography_quarantine' FROM homes.proyecto WHERE id='legacy:1'")
            self.assertEqual(cur.fetchone(), (4000000, 400000, False))
        # The same input can recover once the implementation is corrected.
        self.migrate()

    def test_failure_after_quarantine_rolls_back_original_fields(self):
        broken = MIGRATION.read_text().replace("-- These CHECKs", "SELECT 1/0;\n-- These CHECKs")
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            self.migrate(broken)
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("SELECT lat,lng,raw_features_json ? '_geography_quarantine' FROM homes.proyecto WHERE id='legacy:1'")
            self.assertEqual(cur.fetchone(), (4000000, 400000, False))
            cur.execute("SELECT lat::text,lng,raw_json ? '_geography_quarantine' FROM homes.licencia WHERE id='legacy:lic'")
            self.assertEqual(cur.fetchone(), ("NaN", 400000, False))
        self.migrate()

    @unittest.skipUnless(os.getenv("H03_SEMANTICS_ROOT"), "optional integration with actual PR #857 checkout")
    def test_actual_h02_replay_on_quarantined_old_outlier_then_h01_raw_update(self):
        self.migrate()
        replay = semantics_replay(Path(os.environ["H03_SEMANTICS_ROOT"]))
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 1)
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 0)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE homes.proyecto SET raw_features_json=jsonb_set(raw_features_json, '{_entity_policy}', %s) WHERE id='legacy:1'", (Json({"status": "reviewed"}),))
        self.conn.commit()
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 0)
        with self.conn.cursor() as cur:
            cur.execute("SELECT lat,lng,fase_normalizada,raw_features_json, (SELECT COUNT(*) FROM homes.proyecto_semantica_version) FROM homes.proyecto WHERE id='legacy:1'")
            lat, lng, phase, raw, versions = cur.fetchone()
            self.assertEqual((lat, lng, phase, versions), (None, None, "informacion_publica", 1))
            self.assertEqual(raw["_geography_quarantine"]["original"]["lat"], 4000000)
            self.assertEqual(raw["_entity_policy"]["status"], "reviewed")


if __name__ == "__main__":
    unittest.main()
