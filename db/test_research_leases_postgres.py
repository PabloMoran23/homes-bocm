"""Destructive tests ONLY on an isolated TEST_RESEARCH_DB_URL database."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import unittest
import uuid
from unittest.mock import patch

import psycopg2
from psycopg2.extras import Json
import research_lease as leases
from save_proyecto_info_extra import save

ROOT = Path(__file__).resolve().parents[1]


def payload(project):
    return {'proyecto_id': project, 'estado': 'completa', 'resumen': 'Historia y situación documentada. ' * 30,
            'huecos': 'Constructor no localizado', 'datos': [{
                'bloque': 'situacion', 'clave': 'nombre_publico', 'etiqueta': 'Nombre', 'valor': 'Sector Norte',
                'confianza': 'alta', 'fuente_tipo': 'oficial', 'fuente_nombre': 'Ayuntamiento',
                'fuente_url': 'https://example.org/plan', 'destacado': True}],
            'hallazgos': [{'titulo': 'Contexto', 'cuerpo': 'Contenido extenso de la fuente'}]}


@unittest.skipUnless(os.getenv('TEST_RESEARCH_DB_URL'), 'requires isolated PostgreSQL')
class LeaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ['TEST_RESEARCH_DB_URL']
        cls.env = patch.dict(os.environ, {'SUPABASE_DB_URL': cls.url})
        cls.env.start()
        cls.conn = psycopg2.connect(cls.url)
        with cls.conn, cls.conn.cursor() as c:
            c.execute('DROP SCHEMA IF EXISTS homes CASCADE; CREATE SCHEMA homes')
            for role in ('anon', 'authenticated', 'service_role'):
                c.execute(f'DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$')
            c.execute('''CREATE TABLE homes.proyecto (id text PRIMARY KEY, denominacion text,
                bocm_primary_id text, expediente_grupo text, num_viviendas_max int,
                metric_num_viviendas_max int, bocm_num_viviendas_max int, sup_total_m2 float,
                metric_sup_total_m2 float, bocm_sup_total_m2 float, updated_at timestamptz)''')
            c.execute((ROOT/'supabase/migrations/20260926160000_proyecto_info_extra.sql').read_text())
            c.execute('DROP TABLE IF EXISTS public.homes_analytics_events CASCADE')
            c.execute('''CREATE TABLE public.homes_analytics_events (session_id uuid,page_id uuid,
                event_name text,path text,props jsonb NOT NULL DEFAULT '{}'::jsonb)''')
            c.execute((ROOT/'supabase/migrations/20261017120000_research_leases.sql').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.env.stop()

    def setUp(self):
        with self.conn, self.conn.cursor() as c:
            c.execute('TRUNCATE homes.proyecto CASCADE; TRUNCATE public.homes_analytics_events')
            c.execute("INSERT INTO homes.proyecto(id,num_viviendas_max) VALUES ('large',10000),('small',1)")

    def sql(self, statement, args=()):
        with self.conn, self.conn.cursor() as c:
            c.execute(statement, args)
            return c.fetchall() if c.description else None

    def expire(self, project):
        self.sql("UPDATE homes.proyecto_investigacion_lease SET expires_at=clock_timestamp()-interval '1 second' WHERE proyecto_id=%s", (project,))

    def test_concurrent_claim_cursor_luna(self):
        barrier = threading.Barrier(8)
        def worker(i):
            barrier.wait()
            return leases.claim(('cursor:' if i==0 else 'luna:')+str(i))
        with ThreadPoolExecutor(8) as ex:
            result = list(ex.map(worker, range(8)))
        chosen = [r['proyecto_id'] for r in result if r]
        self.assertEqual(len(chosen), len(set(chosen)))
        self.assertEqual(set(chosen), {'large', 'small'})

    def test_expiry_fences_old_owner_and_renew_recovers_after_crash(self):
        old = leases.claim('cursor')
        leases.maintain('large', 'cursor', old['token'])
        self.expire('large')
        new = leases.claim('luna')
        self.assertNotEqual(old['token'], new['token'])
        for fn in (lambda: leases.maintain('large', 'cursor', old['token']),
                   lambda: leases.maintain('large', 'cursor', old['token'], release=True),
                   lambda: save(payload('large'), owner='cursor', token=old['token'])):
            with self.assertRaises((ValueError,RuntimeError)):
                fn()
        save(payload('large'), owner='luna', token=new['token'])

    def test_idempotence_partial_exclusion_and_no_duplicate_rows(self):
        l = leases.claim('luna')
        data = payload('large'); data['estado'] = 'parcial'
        first = save(data, owner='luna', token=l['token'])
        self.assertEqual(save(data, owner='luna', token=l['token']), first)
        other = copy.deepcopy(data); other['resumen'] += ' cambio'
        with self.assertRaisesRegex(ValueError, 'distinto'):
            save(other, owner='luna', token=l['token'])
        self.assertEqual(leases.claim('cursor')['proyecto_id'], 'small')
        for table in ('proyecto_investigacion','proyecto_dato_extra','proyecto_hallazgo'):
            self.assertEqual(self.sql(f'SELECT count(*) FROM homes.{table}')[0][0], 1)

    def test_atomic_rollback_of_all_three_tables(self):
        l=leases.claim('cursor'); data=payload('large')
        data['hallazgos'][0]['fuente_fecha']='this-is-not-a-date'
        with self.assertRaises(psycopg2.Error):
            save(data, owner='cursor', token=l['token'])
        for table in ('proyecto_investigacion','proyecto_dato_extra','proyecto_hallazgo'):
            self.assertEqual(self.sql(f'SELECT count(*) FROM homes.{table}')[0][0], 0)
        self.assertIsNone(self.sql('SELECT investigacion_id FROM homes.proyecto_investigacion_lease')[0][0])
        data['hallazgos'][0]['fuente_fecha']=None
        save(data, owner='cursor', token=l['token'])

    def test_expiry_during_save_rolls_back_everything(self):
        l=leases.claim('luna')
        self.sql("""CREATE FUNCTION homes.expire_during_dato() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN UPDATE homes.proyecto_investigacion_lease
            SET expires_at=clock_timestamp()-interval '1 second' WHERE proyecto_id=NEW.proyecto_id;
          RETURN NEW; END $$""")
        self.sql("""CREATE TRIGGER expire_during_dato AFTER INSERT ON homes.proyecto_dato_extra
                    FOR EACH ROW EXECUTE FUNCTION homes.expire_during_dato()""")
        try:
            with self.assertRaisesRegex(ValueError,'durante'):
                save(payload('large'),owner='luna',token=l['token'])
            for table in ('proyecto_investigacion','proyecto_dato_extra','proyecto_hallazgo'):
                self.assertEqual(self.sql(f'SELECT count(*) FROM homes.{table}')[0][0],0)
        finally:
            self.sql('DROP TRIGGER expire_during_dato ON homes.proyecto_dato_extra')
            self.sql('DROP FUNCTION homes.expire_during_dato()')

    def test_trigger_rejects_legacy_inserts_and_stale_tokens(self):
        l=leases.claim('luna')
        with self.assertRaises(psycopg2.Error):
            self.sql("INSERT INTO homes.proyecto_investigacion(proyecto_id,estado,resumen) VALUES ('large','parcial','legacy')")
        self.expire('large')
        with self.assertRaises(ValueError):
            save(payload('large'), owner='luna', token=l['token'])

    def test_concurrent_save_retry(self):
        l=leases.claim('luna')
        with ThreadPoolExecutor(8) as ex:
            ids=list(ex.map(lambda _:save(payload('large'),owner='luna',token=l['token']),range(8)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_dato_extra')[0][0],1)

    def test_skip_and_release(self):
        l=leases.claim('luna')
        leases.maintain('large','luna',l['token'],release=True,skip_reason='Ordenanza sin actuación')
        small=leases.claim('cursor')
        self.assertEqual(small['proyecto_id'],'small')
        leases.maintain('small','cursor',small['token'],release=True)
        self.assertEqual(leases.claim('luna')['proyecto_id'],'small')

    def events(self,path,traffic=None,active=10,pages=1,action=None):
        sid=str(uuid.uuid4()); page=str(uuid.uuid4())
        props={} if traffic is None else {'traffic_type':traffic}
        self.sql('INSERT INTO public.homes_analytics_events VALUES (%s,%s,%s,%s,%s)',
                 (sid,page,'page_view',path,Json(props)))
        self.sql('INSERT INTO public.homes_analytics_events VALUES (%s,%s,%s,%s,%s)',
                 (sid,page,'page_engagement',path,Json({'active_seconds':active})))
        for _ in range(pages-1):
            self.sql('INSERT INTO public.homes_analytics_events VALUES (%s,%s,%s,%s,%s)',
                     (sid,str(uuid.uuid4()),'page_view','/mapa',Json({})))
        if action:
            self.sql('INSERT INTO public.homes_analytics_events VALUES (%s,%s,%s,%s,%s)',
                     (sid,page,action,path,Json({})))
        return sid

    def test_human_priority_then_existing_order(self):
        self.events('/proyecto/small')
        self.assertEqual(leases.claim('luna')['proyecto_id'],'small')
        self.assertEqual(leases.claim('cursor')['proyecto_id'],'large')

    def test_bot_admin_unclassified_idle_and_over100_never_prioritized(self):
        for kind in ('bot','admin'):
            self.events('/proyecto/small',traffic=kind)
        self.events('/proyecto/small',active=0)
        self.events('/proyecto/small',active=10,pages=101)
        sid=self.events('/proyecto/small')
        self.sql('INSERT INTO public.homes_analytics_events VALUES (%s,%s,%s,%s,%s)',
                 (sid,str(uuid.uuid4()),'page_view','/admin/analitica',Json({})))
        self.assertEqual(self.sql('SELECT * FROM homes.research_human_project_visits'),[])
        self.assertEqual(leases.claim('luna')['proyecto_id'],'large')

    def test_exact_encoded_alias_sigma_and_ambiguous_paths(self):
        self.sql("INSERT INTO homes.proyecto(id,bocm_primary_id,expediente_grupo) VALUES ('bocm:abc','abc',NULL),('135/2021/00618',NULL,'135/2021/00618')")
        for path in ('/proyecto/bocm%3Aabc','/proyecto/abc','/proyecto/135-2021-00618',
                     '/proyecto/135%2F2021%2F00618'):
            self.events(path)
        self.events('/proyecto/small%ZZ')
        self.events('/proyectos/small')
        self.events('/proyecto/small?foo=1')
        rows=dict(self.sql('SELECT proyecto_id,human_sessions FROM homes.research_human_project_visits'))
        self.assertEqual(rows,{'bocm:abc':2,'135/2021/00618':2})
        self.sql("INSERT INTO homes.proyecto(id,bocm_primary_id) VALUES ('another','abc')")
        self.assertEqual(dict(self.sql('SELECT proyecto_id,human_sessions FROM homes.research_human_project_visits'))['bocm:abc'],1)

    def test_human_activity_click_or_multipage_matches_existing_definition(self):
        self.events('/proyecto/small',active=0,pages=2)
        self.events('/proyecto/small',active=0,action='document_click')
        self.assertEqual(self.sql('SELECT human_sessions FROM homes.research_human_project_visits'),[(2,)])


if __name__ == '__main__':
    unittest.main()
