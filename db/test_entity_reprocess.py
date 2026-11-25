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
from entity_reprocess import (
    activate_policy, activate_policy_bounded, ensure_replay_schema, ensure_schema, enqueue_stale,
    enqueue_stale_bounded, replay_batch, reprocess_queue, require_policy_active,
)
from ingest import _publish_madrid, portal_proyecto_row, save_proyectos, save_licencias
from municipio.entity_policy import POLICY_VERSION
from municipio.manifest import load_manifest

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

    def test_rollout_replays_legacy_nulls_and_updates_snapshot_producer(self):
        self.legacy_without_policy()
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO homes.proyecto(id,denominacion,raw_features_json)
                VALUES ('legacy-null','Formulario urbanístico',NULL),
                       ('legacy-json-null','Formulario urbanístico','null'),
                       ('legacy-scalar','Formulario urbanístico','"texto original"')""")
            cur.execute("""INSERT INTO homes.licencia(id,licencia_key,raw_json)
                VALUES (9223372036854775806,'legacy-license','null')""")
            cur.execute("""CREATE TABLE homes.portal_snapshot(name text PRIMARY KEY, payload jsonb);
                INSERT INTO homes.portal_snapshot VALUES ('web_summary','{"projects":4}');
                CREATE FUNCTION homes.compute_web_summary() RETURNS jsonb LANGUAGE sql AS $$
                    SELECT jsonb_build_object('projects', count(*)) FROM homes.proyecto $$;
                CREATE FUNCTION homes.refresh_map_card_snapshots() RETURNS void LANGUAGE sql AS $$
                    UPDATE homes.portal_snapshot SET payload=homes.compute_web_summary()
                    WHERE name='web_summary' $$;
                CREATE FUNCTION homes.web_summary() RETURNS jsonb LANGUAGE sql STABLE AS $$
                    SELECT payload FROM homes.portal_snapshot WHERE name='web_summary' $$""")
        ensure_replay_schema(self.conn)
        self.assertTrue(self.scalar("SELECT has_function_privilege('service_role', 'homes.activate_entity_policy()', 'EXECUTE')"))
        self.assertFalse(self.scalar("""SELECT has_function_privilege('service_role',
            'homes.activate_entity_policy_prepared()', 'EXECUTE')"""))
        with self.conn.cursor() as cur:
            # The legacy bootstrap normally discovers this proof already; force
            # bounded discovery to find it independently in a later ID range.
            cur.execute("DELETE FROM homes.entity_reprocess_queue WHERE entity_id='legacy-scalar'")

        class UncommittedFixture:
            def cursor(proxy, *args, **kwargs):
                return self.conn.cursor(*args, **kwargs)

            def commit(proxy):
                pass  # Keep the fixture local to this test's transaction.

        with patch("entity_reprocess.SCAN_BATCH_SIZE", 2):
            enqueue_stale_bounded(UncommittedFixture())
        with patch("entity_reprocess.reprocess_queue", side_effect=AssertionError("unexpected row fallback")):
            self.assertEqual(replay_batch(self.conn)["processed"], 5)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)
        self.assertEqual(self.scalar("""SELECT raw_features_json->>'_legacy_entity_raw'
            FROM homes.proyecto WHERE id='legacy-scalar'"""), "texto original")
        self.assertEqual(self.scalar("""SELECT count(*) FROM homes.proyecto
            WHERE raw_features_json->'_entity_policy'->>'version'=%s""", (POLICY_VERSION,)), 4)
        self.assertEqual(self.scalar("""SELECT raw_json->'_entity_policy'->>'version'
            FROM homes.licencia WHERE id=9223372036854775806"""), POLICY_VERSION)
        self.assertEqual(self.scalar("SELECT homes.web_summary()"), {"projects": 4})

        with patch("entity_reprocess.SCAN_BATCH_SIZE", 2):
            activate_policy_bounded(self.conn)
        self.assertEqual(self.scalar("SELECT homes.web_summary()"), {"projects": 1})
        with self.conn.cursor() as cur:
            require_policy_active(cur)
        self.assertIn("FROM homes.portal_snapshot", self.scalar(
            "SELECT pg_get_functiondef('homes.web_summary()'::regprocedure)"))

    def test_bounded_activation_rejects_any_unprepared_range(self):
        self.legacy_without_policy()
        ensure_replay_schema(self.conn)
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM homes.entity_reprocess_queue")
        with self.assertRaisesRegex(RuntimeError, "candidatos sin preparar"):
            activate_policy_bounded(self.conn)
        self.assertFalse(self.scalar("SELECT active FROM homes.entity_policy_config"))

    def test_prepared_activation_requires_source_locks(self):
        with self.conn.cursor() as cur:
            cur.execute((ROOT / "supabase/migrations/20261125200000_entity_policy_bounded_activation.sql").read_text())
        with self.assertRaisesRegex(psycopg2.Error, "requires both table locks"):
            self.scalar("SELECT homes.activate_entity_policy_prepared()")

    def test_madrid_sigma_batch_activates_the_written_projects_only(self):
        self.add("unrelated")
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id) VALUES ('proyecto','unrelated')")
        rows = [
            portal_proyecto_row({
                "id": key, "titulo": "Plan parcial Sector 12", "expediente": "2026/12",
                "url": "https://example/exp/12", "fuente": "sigma",
            }, slug="madrid", nombre="Madrid")
            for key in ("sigma-a", "sigma-b")
        ]
        self.assertEqual(save_proyectos(rows, conn=self.conn), 2)
        self.assertEqual(self.scalar("""SELECT count(*) FROM homes.proyecto
            WHERE id=ANY(%s) AND raw_features_json#>>'{_entity_policy,active,version}'=%s""",
            (["sigma-a", "sigma-b"], POLICY_VERSION)), 2)
        self.assertEqual(self.scalar("SELECT array_agg(entity_id) FROM homes.entity_reprocess_queue"), ["unrelated"])

    def test_madrid_retry_keeps_committed_batches_and_only_marks_a_complete_refresh(self):
        manifest = load_manifest("madrid")

        def delete_committed_fixture():
            with psycopg2.connect(**self.params) as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM homes.proyecto WHERE id LIKE 'batch-%'")
                cur.execute("DELETE FROM homes.ingest_run WHERE municipio_slug='madrid'")
                cur.execute("UPDATE homes.municipio SET last_ingest_at=NULL WHERE slug='madrid'")

        self.addCleanup(delete_committed_fixture)
        projects = [
            portal_proyecto_row({"id": f"batch-{i}", "titulo": "Plan parcial", "fuente": "sigma"},
                                slug="madrid", nombre="Madrid")
            for i in range(101)
        ]
        real_save = save_proyectos

        def fail_last(batch, *, conn, semantic_history_prepared):
            if len(batch) == 1:
                raise RuntimeError("second batch failed")
            return real_save(batch, conn=conn, semantic_history_prepared=semantic_history_prepared)

        with patch("ingest.connect", side_effect=lambda: psycopg2.connect(**self.params)):
            with patch("ingest.save_proyectos", side_effect=fail_last):
                with self.assertRaisesRegex(RuntimeError, "second batch failed"):
                    _publish_madrid(manifest, projects, [], [], [], projects_only=False)
            self.assertEqual(self.scalar("SELECT count(*) FROM homes.proyecto WHERE id LIKE 'batch-%%'"), 100)
            self.assertIsNone(self.scalar("SELECT last_ingest_at FROM homes.municipio WHERE slug='madrid'"))
            self.assertEqual(self.scalar("SELECT array_agg(status ORDER BY id) FROM homes.ingest_run"), ["error"])
            with patch("db.madrid_license_snapshot.sync_snapshot", return_value={"status": "unchanged", "rows": 2}):
                result = _publish_madrid(manifest, projects, [], [], [], projects_only=False)

        self.assertEqual(result["upserted"]["proyecto"], 1)
        self.assertIsNotNone(self.scalar("SELECT last_ingest_at FROM homes.municipio WHERE slug='madrid'"))
        self.assertEqual(self.scalar("SELECT array_agg(status ORDER BY id) FROM homes.ingest_run"), ["error", "ok"])

    def test_madrid_retries_only_the_failed_transaction_and_prepares_history_once(self):
        manifest = load_manifest("madrid")

        def delete_fixture():
            with psycopg2.connect(**self.params) as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM homes.proyecto WHERE id LIKE 'retry-%'")
                cur.execute("DELETE FROM homes.ingest_run WHERE municipio_slug='madrid'")

        self.addCleanup(delete_fixture)
        projects = [
            portal_proyecto_row({"id": f"retry-{i}", "titulo": "Plan parcial", "fuente": "sigma"},
                                slug="madrid", nombre="Madrid")
            for i in range(101)
        ]
        lengths = []

        def temporarily_interrupted(batch, *, conn, semantic_history_prepared):
            self.assertTrue(semantic_history_prepared)
            lengths.append(len(batch))
            if len(lengths) == 3:
                raise psycopg2.errors.ReadOnlySqlTransaction("transient read-only routing")
            count = save_proyectos(batch, conn=conn, semantic_history_prepared=semantic_history_prepared)
            if len(lengths) == 2:
                raise psycopg2.errors.QueryCanceled("transient timeout")
            return count

        from ingest import _ensure_semantic_history
        with (patch("ingest.connect", side_effect=lambda: psycopg2.connect(**self.params)) as connect,
              patch("ingest.save_proyectos", side_effect=temporarily_interrupted),
              patch("ingest._ensure_semantic_history", wraps=_ensure_semantic_history) as prepare,
              patch("ingest.time.sleep")):
            result = _publish_madrid(manifest, projects, [], [], [], projects_only=True)
        self.assertEqual(lengths, [100, 1, 1, 1])
        self.assertEqual(connect.call_count, 2)
        prepare.assert_called_once()
        self.assertEqual(result["upserted"]["proyecto"], 101)
        self.assertEqual(self.scalar("""SELECT count(*) FROM homes.proyectos_historico
            WHERE proyecto_id LIKE 'retry-%%'"""), 101)
        self.assertEqual(self.scalar("SELECT array_agg(status ORDER BY id) FROM homes.ingest_run"), ["ok"])

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
        self.add(descripcion="Documento original de ordenación del ámbito Norte")
        original_contract = self.scalar("SELECT raw_features_json->'_semantic_contract' FROM homes.proyecto")
        self.assertEqual(original_contract["description"]["value"], "Documento original de ordenación del ámbito Norte")
        self.scalar("INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id) VALUES ('proyecto','valid') RETURNING entity_id")
        self.assertEqual(reprocess_queue(self.conn)["processed"], 1)
        self.assertEqual(self.scalar("SELECT raw_features_json->'_semantic_contract' FROM homes.proyecto"), original_contract)
        self.assertEqual(reprocess_queue(self.conn)["processed"], 0)
        self.scalar("UPDATE homes.proyecto SET updated_at=now(), num_viviendas_max=123 WHERE id='valid' RETURNING id")
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)

    def test_municipal_writes_leave_unrelated_backlog_and_identical_rows_untouched(self):
        self.add("unrelated")
        self.scalar("INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id) VALUES ('proyecto','unrelated') RETURNING entity_id")
        record = {"id": "incremental-license", "titulo": "Obras de viviendas",
                  "expediente": "2026/12", "url": "https://example/12",
                  "municipio_slug": "madrid", "fuente": "ayuntamiento",
                  "estado": "concedida", "fecha_concesion": "2026-10-14"}
        self.assertEqual(save_licencias([record], conn=self.conn), 1)
        first = self.scalar("SELECT raw_json FROM homes.licencia WHERE licencia_key='incremental-license'")
        self.assertEqual(first["_entity_policy"]["version"], POLICY_VERSION)
        # An old timestamp proves a repeat does not execute an UPDATE, even
        # though the source lacks the classifier's stored active snapshot.
        self.scalar("UPDATE homes.licencia SET updated_at='2000-01-01' WHERE licencia_key='incremental-license' RETURNING id")
        self.assertEqual(save_licencias([record], conn=self.conn), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue WHERE entity_table='licencia'"), 0)
        self.assertEqual(self.scalar("SELECT extract(year FROM updated_at) FROM homes.licencia WHERE licencia_key='incremental-license'"), 2000)
        self.assertEqual(save_licencias([{**record, "titulo": "Formulario de obras"}], conn=self.conn), 1)
        self.assertEqual(self.scalar("SELECT raw_json->'_entity_policy'->>'entity_type' FROM homes.licencia WHERE licencia_key='incremental-license'"), "tramite_reutilizable")
        self.add("municipal-new")
        self.assertEqual(self.scalar("SELECT array_agg(entity_id) FROM homes.entity_reprocess_queue"), ["unrelated"])

    def test_incremental_license_classification_includes_all_insert_pages(self):
        rows = [{"id": f"paged-{i}", "titulo": "Obras de viviendas",
                 "fuente": "ayuntamiento", "municipio_slug": "madrid",
                 "expediente": f"2026/{i}", "url": f"https://example/{i}"}
                for i in range(205)]
        self.assertEqual(save_licencias(rows, conn=self.conn), 205)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.licencia WHERE raw_json->'_entity_policy'->>'version'=%s", (POLICY_VERSION,)), 205)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)
        self.assertEqual(save_licencias(rows, conn=self.conn), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.entity_reprocess_queue"), 0)

    def test_municipal_batch_preserves_failed_record_and_classifies_the_rest(self):
        from entity_reprocess import _metadata

        self.scalar("INSERT INTO homes.municipio(slug,nombre) VALUES ('toledo','Toledo') RETURNING slug")

        def classify(row, table, version, reason):
            if row["id"] == "batch-invalid":
                raise ValueError("unclassifiable record")
            return _metadata(row, table, version, reason)

        rows = [
            portal_proyecto_row(
                {"id": identity, "titulo": "Plan parcial Sector 12", "expediente": "2026/12"},
                slug="toledo", nombre="Toledo",
            )
            for identity in ("batch-invalid", "batch-valid")
        ]
        with patch("entity_reprocess._metadata", side_effect=classify):
            self.assertEqual(save_proyectos(rows, conn=self.conn), 2)
        self.assertEqual(
            self.scalar("SELECT entity_id FROM homes.entity_reprocess_queue WHERE attempts=1"),
            "batch-invalid",
        )
        self.assertEqual(
            self.scalar("""SELECT raw_features_json->'_entity_policy'->'active'->>'version'
                            FROM homes.proyecto WHERE id='batch-valid'"""),
            POLICY_VERSION,
        )

    def test_interrupted_ingest_session_reports_a_failed_commit(self):
        from ingest import IngestSession

        worker = psycopg2.connect(**self.params)
        recovery = psycopg2.connect(**self.params)
        self.addCleanup(worker.close)
        self.addCleanup(recovery.close)
        with patch("ingest.connect", side_effect=[worker, recovery]):
            with self.assertRaises(psycopg2.InterfaceError):
                with IngestSession("test") as session:
                    worker.close()
        self.assertEqual(
            self.scalar("SELECT status FROM homes.ingest_run WHERE id=%s", (session.run_id,)),
            "error",
        )
        self.scalar("DELETE FROM homes.ingest_run WHERE id=%s RETURNING id", (session.run_id,))
        self.conn.commit()

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

    def test_temporal_quarantine_cannot_establish_a_grant(self):
        common = {"titulo": "Licencia de obras de viviendas", "expediente": "2026/12",
                  "url": "https://example/12", "municipio_slug": "madrid", "source": "madrid-opendata"}
        save_licencias([{**common, "id": "future", "fecha_concesion": "2099-01-01"},
                        {**common, "id": "invalid", "fecha_concesion": "2025-02-30"},
                        {**common, "id": "partial", "fecha_concesion": "2025-02"}], conn=self.conn)
        self.assertIsNone(self.scalar("SELECT fecha_concesion FROM homes.licencia WHERE licencia_key='future'"))
        self.assertEqual(self.scalar("SELECT raw_json->'temporal'->'quarantine'->0->>'reason' FROM homes.licencia WHERE licencia_key='future'"), "future_observed_date")
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.licencia_actividad"), 0)
        self.assertFalse(self.scalar("SELECT (raw_json->'_entity_policy'->>'grant_evidenced')::boolean FROM homes.licencia WHERE licencia_key='future'"))
        # Independent affirmative state still proves a grant, without fabricating its date.
        save_licencias([{**common, "id": "affirmative", "estado": "concedida", "fecha_concesion": "2099-01-01"}], conn=self.conn)
        self.assertEqual(self.scalar("SELECT count(*) FROM homes.licencia_actividad"), 1)
        self.assertIsNone(self.scalar("SELECT fecha_concesion FROM homes.licencia WHERE licencia_key='affirmative'"))

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
        # Explicit source CRS and boundary: the geography guard must validate
        # the fixture just as it validates real records, without network requests.
        geography = {"lat": 40.4, "lng": -3.7, "coordinates_crs": "EPSG:4326",
                     "municipal_boundary": {"type": "Polygon", "coordinates": [[[-3.8,40.3],[-3.6,40.3],[-3.6,40.5],[-3.8,40.5],[-3.8,40.3]]]}}
        self.add(**geography)
        self.add("generic", titulo="Formulario de obras", expediente=None, **geography)
        save_licencias([{"id": "grant", "titulo": "Obras de viviendas", "expediente": "2026/12", "url": "https://example/12", "municipio_slug": "madrid", "fecha_concesion": "2026-10-14", "source": "ayuntamiento", "_territorial_origin": {"adapter": "fixture", "url": "https://example/12", "municipio_slug": "madrid"}, **geography}], conn=self.conn)
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
