"""Isolated PostgreSQL regression; CI provides TEST_SEMANTICS_DB_URL."""
import os
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extras import Json
from reprocess_project_semantics import replay, replay_batch, run_replay
from ingest import _PROYECTO_UPSERT_COLS, portal_proyecto_row, save_proyectos
from datetime import datetime


@unittest.skipUnless(os.getenv("TEST_SEMANTICS_DB_URL"), "requires isolated PostgreSQL")
class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg2.connect(os.environ["TEST_SEMANTICS_DB_URL"])
        with self.conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS homes CASCADE; CREATE SCHEMA homes")
            # The common writer also bootstraps the inactive entity policy, whose
            # schema references both canonical resource tables even for project-only writes.
            cur.execute("DO $$ BEGIN CREATE ROLE service_role; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
            cur.execute("CREATE TABLE homes.licencia (id bigint PRIMARY KEY, raw_json jsonb)")
            cur.execute("""CREATE TABLE homes.proyecto (
                           id text PRIMARY KEY, municipio_slug text, fuente text,
                           raw_features_json jsonb, fase text, fase_normalizada text,
                           fecha_aprob text, bocm_pub_date date, resumen_contenido text,
                           bocm_resumen text, updated_at timestamptz)""")
            cur.execute("""INSERT INTO homes.proyecto (id, municipio_slug, fuente,
                         raw_features_json, fase, fecha_aprob, resumen_contenido)
                         VALUES ('municipal:1', 'parla', 'ayuntamiento', %s,
                                 'Plan parcial', '2026-10-14', 'Plan Norte')""",
                        (Json({"titulo": "Plan Norte", "tipo": "Plan parcial", "fecha": "2026-10-14"}),))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_live_upsert_repeat_and_removal_clears_canonical_values(self):
        row = portal_proyecto_row({"id": "live:1", "titulo": "Plan Norte", "tipo": "Plan parcial",
                                  "fase": "Información pública", "fecha_publicacion": "2026-10-14"},
                                 slug="parla", nombre="Parla")
        # Isolated test table includes the canonical upsert columns without legacy dependencies.
        with self.conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='homes' AND table_name='proyecto'")
            present = {r[0] for r in cur.fetchall()}
            for col in _PROYECTO_UPSERT_COLS:
                if col in present:
                    continue
                value = row.get(col)
                kind = "boolean" if col == "bocm_es_relevante" else "jsonb" if isinstance(value, Json) else "boolean" if isinstance(value, bool) else "timestamptz" if isinstance(value, datetime) else "text"
                cur.execute(f'ALTER TABLE homes.proyecto ADD COLUMN "{col}" {kind}')
        with self.conn:
            save_proyectos([row], conn=self.conn)
            save_proyectos([row], conn=self.conn)
        changed = portal_proyecto_row({"id": "live:1", "titulo": "Plan Norte", "tipo": "Plan parcial", "fecha": "2026-10-15"}, slug="parla", nombre="Parla")
        with self.conn:
            save_proyectos([changed], conn=self.conn)
        with self.conn.cursor() as cur:
            cur.execute("SELECT fase, bocm_pub_date, fecha_aprob FROM homes.proyecto WHERE id='live:1'")
            self.assertEqual(cur.fetchone(), (None, None, None))
            cur.execute("SELECT COUNT(*) FROM homes.proyecto_semantica_version WHERE proyecto_id='live:1'")
            self.assertEqual(cur.fetchone()[0], 2)

    def test_repeat_source_change_rule_change_and_atomic_recovery(self):
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 1)
        with self.conn.cursor() as cur:
            cur.execute("SELECT fase, fecha_aprob, bocm_pub_date FROM homes.proyecto")
            self.assertEqual(cur.fetchone(), (None, None, None))
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 0)
        with self.conn.cursor() as cur:
            cur.execute("""UPDATE homes.proyecto SET raw_features_json=
                         jsonb_set(raw_features_json, '{fase}', '\"Información pública\"')""")
        self.conn.commit()
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with self.conn:
                with patch("reprocess_project_semantics.save_semantic_versions", side_effect=RuntimeError("injected")):
                    replay(self.conn)
        with self.conn:
            self.assertEqual(replay(self.conn)["reprocessed"], 1)
        with patch("project_semantics.TEMPLATE_VERSION", "test/2"), patch("reprocess_project_semantics.TEMPLATE_VERSION", "test/2"):
            with self.conn:
                self.assertEqual(replay(self.conn)["reprocessed"], 1)
            with self.conn:
                self.assertEqual(replay(self.conn)["reprocessed"], 0)
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM homes.proyecto")
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute("SELECT COUNT(*) FROM homes.proyecto_semantica_version")
            self.assertEqual(cur.fetchone()[0], 3)
            cur.execute("SELECT source_record FROM homes.proyecto_semantica_version ORDER BY created_at LIMIT 1")
            self.assertEqual(cur.fetchone()[0]["fecha"], "2026-10-14")

    def test_batch_commit_survives_later_failure_and_restart_is_idempotent(self):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO homes.proyecto(id,municipio_slug,fuente,raw_features_json) VALUES ('municipal:2','parla','ayuntamiento',%s)",
                        (Json({'titulo':'Plan Sur','fase':'Información pública'}),))
        self.conn.commit()
        def factory():
            return psycopg2.connect(self.conn.dsn)
        actual = replay_batch
        def fail_second(conn, **kwargs):
            if kwargs['after_id'] is not None:
                conn.close()
                raise psycopg2.OperationalError('injected connection interruption')
            return actual(conn, **kwargs)
        with patch('reprocess_project_semantics.replay_batch', side_effect=fail_second):
            with self.assertRaisesRegex(psycopg2.OperationalError, 'injected connection interruption'):
                run_replay(batch_size=1, connect_factory=factory)
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM homes.proyecto_semantica_version')
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute("SELECT count(*) FROM homes.proyecto WHERE raw_features_json ? '_semantic_contract'")
            self.assertEqual(cur.fetchone()[0], 1)
        result = run_replay(batch_size=1, connect_factory=factory)
        self.assertTrue(result['complete'])
        self.assertEqual(result['reprocessed'], 1)
        self.assertEqual(run_replay(batch_size=1, connect_factory=factory)['reprocessed'], 0)
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM homes.proyecto_semantica_version')
            self.assertEqual(cur.fetchone()[0], 2)

    def test_history_and_canonical_update_rollback_together(self):
        with self.assertRaises(psycopg2.errors.CheckViolation):
            with self.conn:
                with self.conn.cursor() as cur:
                    cur.execute("ALTER TABLE homes.proyecto ADD CONSTRAINT injected_replay_failure CHECK (NOT (raw_features_json ? '_semantic_contract'))")
                replay_batch(self.conn, batch_size=1)
        with self.conn.cursor() as cur:
            cur.execute("SELECT raw_features_json ? '_semantic_contract',fase FROM homes.proyecto")
            self.assertEqual(cur.fetchone(), (False,'Plan parcial'))
            cur.execute("SELECT to_regclass('homes.proyecto_semantica_version')")
            self.assertIsNone(cur.fetchone()[0])

    def test_bulk_update_preserves_dates_nulls_and_metadata_across_batches(self):
        evidence = {'titulo':'Plan Norte','fase':'Información pública','fecha_publicacion':'2026-10-14',
                    '_geography_quarantine':{'status':'quarantined'},'_entity_policy':{'fixture':'retained'}}
        with self.conn.cursor() as cur:
            cur.execute('UPDATE homes.proyecto SET raw_features_json=%s', (Json(evidence),))
            cur.execute("INSERT INTO homes.proyecto(id,municipio_slug,fuente,raw_features_json) VALUES ('municipal:2','parla','ayuntamiento',%s)", (Json({'titulo':'Plan Sur'}),))
        self.conn.commit()
        result = run_replay(batch_size=2, max_batches=1, connect_factory=lambda:psycopg2.connect(self.conn.dsn))
        self.assertEqual(result['reprocessed'],2)
        self.assertFalse(result['complete'])
        with self.conn.cursor() as cur:
            cur.execute('SELECT id,bocm_pub_date,raw_features_json FROM homes.proyecto ORDER BY id')
            first,second=cur.fetchall()
            self.assertEqual(first[1].isoformat(),'2026-10-14')
            self.assertIsNone(second[1])
            self.assertEqual(first[2]['_geography_quarantine'],evidence['_geography_quarantine'])
            self.assertEqual(first[2]['_entity_policy'],evidence['_entity_policy'])


if __name__ == "__main__":
    unittest.main()
