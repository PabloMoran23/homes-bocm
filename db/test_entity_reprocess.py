"""Transacciones reales. H01_TEST_DB_URL debe apuntar a Postgres local desechable."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg2
from psycopg2.extras import Json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT))
from entity_reprocess import activate_policy, ensure_schema, enqueue_stale, reprocess_queue, require_policy_active
from ingest import portal_proyecto_row, save_proyectos, save_licencias
from municipio.entity_policy import POLICY_VERSION

URL = os.getenv("H01_TEST_DB_URL")


@unittest.skipUnless(URL, "H01_TEST_DB_URL required for local PostgreSQL integration")
class ReprocessIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = psycopg2.extensions.parse_dsn(URL)
        if params.get("host") not in ("localhost", "127.0.0.1", "/tmp/h01-postgres"):
            raise RuntimeError("Tests require disposable local PostgreSQL")
        cls.admin = psycopg2.connect(URL)
        cls.admin.autocommit = True
        cls.database = "h01_test_" + uuid.uuid4().hex
        with cls.admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE {cls.database} TEMPLATE template0 ENCODING 'UTF8'")
        with cls.admin.cursor() as cur:
            for role in ("anon", "authenticated", "service_role"):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if not cur.fetchone():
                    cur.execute(f"CREATE ROLE {role}")
        params["dbname"] = cls.database
        cls.params = params
        conn = psycopg2.connect(**params)
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA homes; SET search_path TO homes,public; CREATE TABLE homes.sigma_programa(programa_id text primary key)")
            cur.execute((ROOT / "db/schema_dominio.sql").read_text())
            cur.execute((ROOT / "supabase/migrations/20260819190000_ingest_schema.sql").read_text())
            # Actual production RPC definition, not a copy of the policy.
            src = (ROOT / "supabase/migrations/20250602160000_rpc_dominio.sql").read_text()
            rpc = src[src.index("CREATE OR REPLACE FUNCTION homes.get_proyecto_portal"):src.index("CREATE OR REPLACE FUNCTION public.get_proyecto_portal")]
            cur.execute(rpc)
            cur.execute("""CREATE FUNCTION homes._proyecto_map_portal_row(p homes.proyecto) RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT jsonb_build_object('id',p.id) $$;
                CREATE FUNCTION homes.map_cm_portal() RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT jsonb_agg(homes._proyecto_map_portal_row(p)) FROM homes.proyecto p $$;
                CREATE FUNCTION homes.madrid_dashboard_stats() RETURNS bigint LANGUAGE sql STABLE AS $$ SELECT count(*) FROM homes.licencia $$""")
            cur.execute((ROOT / "supabase/migrations/20261014235900_entity_activity_policy.sql").read_text())
        activate_policy(conn)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        with cls.admin.cursor() as cur:
            cur.execute(f"DROP DATABASE {cls.database}")
        cls.admin.close()

    def setUp(self):
        self.conn = psycopg2.connect(**self.params)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def scalar(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def add(self, identity="valid", **fields):
        rec = {"id": identity, "titulo": "Plan parcial Sector 12", "expediente": "2026/12", "url": "https://example/exp/12", **fields}
        row = portal_proyecto_row(rec, slug="madrid", nombre="Madrid")
        save_proyectos([row], conn=self.conn)
        return rec

    def legacy_without_policy(self):
        with self.conn.cursor() as cur:
            cur.execute("""DROP TRIGGER entity_classification_changed ON homes.proyecto;
                DROP TRIGGER entity_classification_changed ON homes.licencia;
                DROP VIEW homes.proyecto_actividad CASCADE; DROP VIEW homes.licencia_actividad CASCADE;
                DROP FUNCTION homes.activate_entity_policy();
                DROP TABLE homes.entity_policy_config CASCADE; DROP TABLE homes.entity_reprocess_queue CASCADE;""")
            src = (ROOT / "supabase/migrations/20250602160000_rpc_dominio.sql").read_text()
            cur.execute(src[src.index("CREATE OR REPLACE FUNCTION homes.get_proyecto_portal"):src.index("CREATE OR REPLACE FUNCTION public.get_proyecto_portal")])
            cur.execute("INSERT INTO homes.proyecto(id,denominacion,enlace,raw_features_json) VALUES ('legacy','Plan parcial Sector 12','https://example/12',%s)",
                        (Json({"expediente": "2026/12"}),))

    def test_code_first_bootstraps_without_aborting_ingestion_or_cutting_reads(self):
        self.legacy_without_policy()
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        self.add("new")  # bootstrap occurs before any new project write
        save_licencias([{"id": "new-license", "titulo": "Obras de viviendas", "expediente": "2026/12", "url": "https://example/12", "estado": "concedida"}], conn=self.conn)
        self.assertFalse(self.scalar("SELECT active FROM homes.entity_policy_config"))
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        with self.conn.cursor() as cur:
            with self.assertRaisesRegex(RuntimeError, "control_active=false"):
                require_policy_active(cur)
        reprocess_queue(self.conn)
        activate_policy(self.conn)
        self.assertTrue(self.scalar("SELECT active FROM homes.entity_policy_config"))
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('new')"))

    def test_migration_first_keeps_legacy_reads_during_failure_then_activates_atomically(self):
        self.legacy_without_policy()
        ensure_schema(self.conn)
        self.assertFalse(self.scalar("SELECT active FROM homes.entity_policy_config"))
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        with patch("entity_reprocess.annotate", side_effect=RuntimeError("temporary failure")):
            self.assertEqual(reprocess_queue(self.conn)["failed"], 1)
        self.scalar("SAVEPOINT premature_activation; SELECT 1")
        with self.assertRaisesRegex(psycopg2.Error, "entity_policy_not_ready"):
            activate_policy(self.conn)
        self.scalar("ROLLBACK TO SAVEPOINT premature_activation; SELECT 1")
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        reprocess_queue(self.conn)
        activate_policy(self.conn)
        self.assertTrue(self.scalar("SELECT active FROM homes.entity_policy_config"))
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('legacy')"))
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)

    def test_rule_upgrade_preserves_active_snapshot_until_atomic_switch(self):
        self.add()
        with patch("entity_reprocess.POLICY_VERSION", "next"), patch("municipio.entity_policy.POLICY_VERSION", "next"):
            enqueue_stale(self.conn)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)
            self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('valid')"))
            reprocess_queue(self.conn)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)
            self.assertEqual(self.scalar("SELECT version FROM homes.entity_policy_config"), POLICY_VERSION)
            activate_policy(self.conn)
            self.assertEqual(self.scalar("SELECT version FROM homes.entity_policy_config"), "next")
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)

    def test_upsert_recurrence_resources_and_publication_rpc(self):
        self.add()
        self.add()
        self.add("generic", titulo="Formulario de obras", expediente=None)
        self.add("unknown", titulo="Área A", expediente=None)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto"), 3)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)
        self.assertIsNotNone(self.scalar("SELECT homes.get_proyecto_portal('valid')"))
        self.assertIsNone(self.scalar("SELECT homes.get_proyecto_portal('generic')"))
        self.assertEqual(self.scalar("SELECT homes.map_cm_portal()"), [{"id": "valid"}])

    def test_changed_source_queued_hidden_reclassified_and_recoverable(self):
        self.add()
        self.scalar("UPDATE homes.proyecto SET raw_features_json=%s,denominacion='Formulario de obras' WHERE id='valid' RETURNING id",
                    (Json({"titulo": "Formulario de obras", "url": "https://example/catalog/x", "original_document": "kept"}),))
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        result = reprocess_queue(self.conn)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.scalar("SELECT raw_features_json->>'original_document' FROM homes.proyecto"), "kept")
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        self.add()
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)

    def test_policy_version_reprocess_without_duplication(self):
        self.add()
        self.scalar("UPDATE homes.entity_policy_config SET version='obsolete' RETURNING version")
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        with patch("entity_reprocess.POLICY_VERSION", "next"), patch("municipio.entity_policy.POLICY_VERSION", "next"):
            enqueue_stale(self.conn)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
            reprocess_queue(self.conn)
            activate_policy(self.conn)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto"), 1)

    def test_failed_classification_preserves_queue_and_retry_recovers(self):
        self.scalar("INSERT INTO homes.proyecto(id,denominacion,enlace,raw_features_json) VALUES ('retry','Plan parcial Sector 12','https://example/12',%s) RETURNING id", (Json({"expediente": "2026/12"}),))
        with patch("entity_reprocess.annotate", side_effect=RuntimeError("classifier unavailable")):
            self.assertEqual(reprocess_queue(self.conn)["failed"], 1)
        self.assertEqual(self.scalar("SELECT failed FROM homes.entity_policy_health"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        self.assertEqual(reprocess_queue(self.conn)["processed"], 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 1)

    def test_other_raw_contract_preserved_and_worker_update_not_requeued(self):
        self.add(_semantic_contract={"title": "source original"})
        self.assertEqual(self.scalar("SELECT raw_features_json->'_semantic_contract' FROM homes.proyecto"), {"title": "source original"})
        self.assertEqual(reprocess_queue(self.conn)["processed"], 0)
        self.scalar("UPDATE homes.proyecto SET updated_at=now(), num_viviendas_max=123 WHERE id='valid' RETURNING id")
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)

    def test_licenses_do_not_promote_date_or_foreign_categories(self):
        common = {"titulo": "Obras de viviendas", "expediente": "2026/12", "url": "https://example/12", "municipio_slug": "madrid"}
        save_licencias([{**common, "id": "request", "fecha": "2026-10-14"},
                        {**common, "id": "grant", "fecha_concesion": "2026-10-14"},
                        {**common, "id": "taxi", "titulo": "Licencia de taxi", "fecha_concesion": "2026-10-14"},
                        {**common, "id": "denied", "titulo": "Denegación de concesión de licencia de obras", "estado": "denegada", "fecha_concesion": "2026-10-14"},
                        {**common, "id": "requested", "titulo": "Solicitud de concesión de licencia de obras", "estado": "solicitada", "fecha_concesion": "2026-10-14"},
                        {**common, "id": "revoked", "titulo": "Revocación de licencia de obras", "estado": "revocada", "fecha_concesion": "2026-10-14"}], conn=self.conn)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.licencia"), 6)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.licencia_actividad"), 1)
        self.assertEqual(self.scalar("SELECT homes.madrid_dashboard_stats()"), 1)
        self.assertIsNone(self.scalar("SELECT fecha_concesion FROM homes.licencia WHERE licencia_key='request'"))

    def test_locked_writer_cannot_lose_a_pending_reclassification(self):
        self.add()
        self.scalar("INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id) VALUES ('proyecto','valid') RETURNING entity_id")
        self.conn.commit()
        writer = psycopg2.connect(**self.params)
        try:
            with writer.cursor() as cur:
                cur.execute("UPDATE homes.proyecto SET raw_features_json=%s WHERE id='valid'",
                            (Json({"titulo": "Formulario de obras", "url": "https://example/catalog/x"}),))
            # Hay escritura abierta simultánea: el worker no espera ni borra cola.
            self.assertEqual(reprocess_queue(self.conn)["processed"], 0)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
            self.conn.commit()
            writer.commit()
            self.assertEqual(reprocess_queue(self.conn)["processed"], 1)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        finally:
            writer.close()
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM homes.proyecto WHERE id='valid'; DELETE FROM homes.entity_reprocess_queue WHERE entity_id='valid'")
            self.conn.commit()

    def test_allowlist_preserves_admin_reads_and_rejects_unknown_signature(self):
        with self.conn.cursor() as cur:
            cur.execute("CREATE FUNCTION homes.audit_resources() RETURNS bigint LANGUAGE sql STABLE AS $$ SELECT count(*) FROM homes.proyecto $$")
        self.add("generic", titulo="Formulario de obras", expediente=None)
        with self.conn.cursor() as cur:
            migration = (ROOT / "supabase/migrations/20261014235900_entity_activity_policy.sql").read_text()
            cur.execute(migration)
            self.assertEqual(self.scalar("SELECT homes.audit_resources()"), 1)
            cur.execute("SAVEPOINT unexpected_rpc")
            cur.execute("CREATE FUNCTION homes.map_cm_portal(integer) RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT jsonb_agg(p.id) FROM homes.proyecto p $$")
            with self.assertRaisesRegex(psycopg2.Error, "Firma RPC inesperada"):
                activate_policy(self.conn)
            cur.execute("ROLLBACK TO SAVEPOINT unexpected_rpc")

    def test_municipal_map_exports_use_same_activity_views(self):
        import tempfile
        from psycopg2.extras import RealDictCursor
        from export_cm_portal_web import export_proyectos, export_licencias
        self.add(lat=40.4, lng=-3.7)
        self.add("generic", titulo="Formulario de obras", expediente=None, lat=40.4, lng=-3.7)
        save_licencias([{"id": "grant", "titulo": "Obras de viviendas", "expediente": "2026/12", "url": "https://example/12", "municipio_slug": "madrid", "fecha_concesion": "2026-10-14", "lat": 40.4, "lng": -3.7}], conn=self.conn)
        with tempfile.TemporaryDirectory() as folder, self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            points, polygons, stats = export_proyectos(cur, Path(folder), "2026-10-14")
            self.assertEqual(points, 1)
            self.assertEqual(export_licencias(cur, Path(folder), "2026-10-14"), 1)

    def test_concurrent_writer_is_hidden_until_new_snapshot_classified(self):
        self.add()
        self.conn.commit()
        other = psycopg2.connect(**self.params)
        try:
            with other.cursor() as cur:
                cur.execute("UPDATE homes.proyecto SET denominacion='Solicitud de aprobación de planeamiento', raw_features_json=%s WHERE id='valid'",
                            (Json({"titulo": "Solicitud de aprobación de planeamiento", "url": "https://example/catalog/x"}),))
            other.commit()
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
            reprocess_queue(self.conn)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto_actividad"), 0)
        finally:
            other.close()
            # Este test hizo commit de la fila para permitir dos conexiones.
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM homes.proyecto WHERE id='valid'; DELETE FROM homes.entity_reprocess_queue WHERE entity_id='valid'")
            self.conn.commit()


if __name__ == "__main__":
    unittest.main()
