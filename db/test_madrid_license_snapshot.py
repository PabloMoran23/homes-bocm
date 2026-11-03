import os
import unittest

from db.madrid_license_snapshot import prepare_row, source_fingerprint, sync_snapshot


def record(key, dataset='640505', **changes):
    return dict(id=key, licencia_key=key, ndp_edificio='110001',
                anio_dataset=2026, fecha_alta='2026-06-01',
                fecha_concesion='2026-10-19' if dataset == '640505' else None,
                source_dataset=dataset, fuente='madrid-opendata', municipio_slug='madrid',
                procedimiento='Licencia', tipo_expediente='Obras', **changes)


class ProvenanceTest(unittest.TestCase):
    def test_fingerprint_normalizes_dates_and_numbers_but_preserves_identity(self):
        raw = dict(anio_dataset=2022, ndp_edificio='110001', fecha_de_alta='01/06/2022',
                   tipo_de_expediente='Obras', proteccion='Antiguo')
        other = dict(raw, anio_dataset='2022.0', fecha_de_alta='2022-06-01', proteccion='Corregido')
        self.assertEqual(source_fingerprint(raw), source_fingerprint(other))
        self.assertNotEqual(source_fingerprint(raw), source_fingerprint(dict(other, ndp_edificio='110002')))

    def test_territorial_conflict_is_rejected_before_annotation(self):
        row = record('a')
        row['municipio_slug'] = 'valladolid'
        with self.assertRaises(ValueError):
            prepare_row(row)

    def test_dates_remain_distinct_and_classification_matches_current_policy(self):
        row = prepare_row(record('a'))
        self.assertEqual(row['fecha_alta'], '2026-06-01')
        self.assertEqual(row['fecha_concesion'], '2026-10-19')
        self.assertEqual(row['_entity_policy']['active']['version'], row['_entity_policy']['version'])


@unittest.skipUnless(os.environ.get('MADRID_SNAPSHOT_TEST_DB_URL'), 'Disposable pg_temp integration tables require explicit test connection')
class SnapshotIntegrationTest(unittest.TestCase):
    def setUp(self):
        import psycopg2
        self.conn = psycopg2.connect(os.environ['MADRID_SNAPSHOT_TEST_DB_URL'])
        with self.conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE licencia (LIKE homes.licencia INCLUDING DEFAULTS INCLUDING INDEXES)')
            cur.execute('''CREATE TEMP TABLE inmueble (id bigserial PRIMARY KEY,ndp_edificio text UNIQUE,
                direccion text,distrito text,barrio text,lat double precision,lng double precision,
                coord_source text,inserted_at timestamptz,updated_at timestamptz)''')
            cur.execute('CREATE TEMP TABLE entity_reprocess_queue(entity_table text,entity_id text)')
            cur.execute("INSERT INTO pg_temp.licencia(id,licencia_key,municipio_slug,fuente,raw_json) VALUES(1,'other','valladolid','other','{}'),(2,'legacy',NULL,NULL,%s)",
                        (__import__('psycopg2.extras', fromlist=['Json']).Json({'anio_dataset':2022,'ndp_edificio':'110001','fecha_de_alta':'2022-06-01'}),))
        self.conn.commit()
        self.records = [record('a'), record('b', '133556')]
        self.evidence = {source_fingerprint({'anio_dataset':2022,'ndp_edificio':'110001','fecha_de_alta':'2022-06-01'})}

    def tearDown(self):
        self.conn.close()

    def test_atomic_replacement_idempotence_and_outside_preservation(self):
        report = sync_snapshot(self.conn, self.records, evidence=self.evidence, apply=True, schema='pg_temp')
        self.assertEqual(report['status'], 'applied')
        self.assertEqual(report['outside_rows_unchanged'], 1)
        self.conn.commit()
        with self.conn.cursor() as cur:
            cur.execute('SELECT licencia_key,inmueble_id FROM pg_temp.licencia ORDER BY id')
            rows = cur.fetchall()
            self.assertEqual(rows[0], ('other', None))
            self.assertTrue(all(r[1] is not None for r in rows[1:]))
            cur.execute('SELECT count(*) FROM pg_temp.madrid_license_snapshot_backup')
            self.assertEqual(cur.fetchone()[0], 1)
        repeated = sync_snapshot(self.conn, self.records, apply=True, schema='pg_temp')
        self.assertEqual(repeated['status'], 'unchanged')
        with self.conn.cursor() as cur:
            cur.execute('SELECT licencia_key,inmueble_id FROM pg_temp.licencia ORDER BY id')
            self.assertEqual(cur.fetchall(), rows)

    def test_duplicate_input_and_failed_insert_leave_original_rows_intact(self):
        with self.assertRaises(ValueError):
            sync_snapshot(self.conn, self.records + self.records, evidence=self.evidence, apply=True, schema='pg_temp')
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("ALTER TABLE pg_temp.licencia ADD CONSTRAINT reject_new CHECK(licencia_key NOT IN ('a','b'))")
        self.conn.commit()
        from psycopg2.errors import CheckViolation
        with self.assertRaises(CheckViolation):
            sync_snapshot(self.conn, self.records, evidence=self.evidence, apply=True, schema='pg_temp')
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute('SELECT licencia_key FROM pg_temp.licencia ORDER BY id')
            self.assertEqual(cur.fetchall(), [('other',), ('legacy',)])
