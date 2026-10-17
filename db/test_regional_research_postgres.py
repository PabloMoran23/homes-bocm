"""Destructive ONLY on isolated TEST_REGIONAL_DB_URL; no model calls."""
import copy
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import psycopg2
import research_asunto as r

ROOT=Path(__file__).resolve().parents[1]
URL='https://oficial.example/plan-1'


def payload(project='p1',document=False):
    nodes=[{'ref':'plan','clave_identidad':'oficial:municipio:PG-1','tipo':'planeamiento',
            'titulo':'Plan general 1','municipio':'Municipio','fuente_url':URL,'extracto':'Identidad del plan 1'}]
    if document:nodes.append({'ref':'doc','clave_identidad':'documento:'+URL+'/'+project,
        'tipo':'documento','titulo':'Plano '+project,'padre_ref':'plan','fuente_url':URL+'/'+project,
        'extracto':'Plano integrante del plan 1','municipio':'Municipio'})
    return {'proyecto_id':project,'tipo_entrada':'documento' if document else 'planeamiento',
            'estado':'completa','resumen':'Contexto y contenido con cronología documentada. '*20,
            'asunto_ref':'doc' if document else 'plan','asuntos':nodes,'relaciones':[],
            'fuentes':[{'url':URL,'extracto':'Referencia oficial del plan','fecha':None}],
            'datos':[],'hallazgos':[],'vinculos_pendientes':[]}


@unittest.skipUnless(os.getenv('TEST_REGIONAL_DB_URL'),'requires isolated PostgreSQL')
class RegionalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=os.environ['TEST_REGIONAL_DB_URL']
        cls.env=patch.dict(os.environ,{'SUPABASE_DB_URL':cls.url});cls.env.start()
        cls.conn=psycopg2.connect(cls.url)
        with cls.conn,cls.conn.cursor() as c:
            c.execute('DROP SCHEMA IF EXISTS homes CASCADE; CREATE SCHEMA homes')
            for role in ('anon','authenticated','service_role'):
                c.execute(f'DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$')
            c.execute('''CREATE TABLE homes.proyecto(id text PRIMARY KEY,denominacion text,municipio text,
              bocm_primary_id text,expediente_grupo text,raw_features_json jsonb,
              num_viviendas_max int,metric_num_viviendas_max int,bocm_num_viviendas_max int,
              sup_total_m2 float,metric_sup_total_m2 float,bocm_sup_total_m2 float,updated_at timestamptz)''')
            c.execute('DROP TABLE IF EXISTS public.homes_analytics_events CASCADE')
            c.execute("CREATE TABLE public.homes_analytics_events(session_id uuid,page_id uuid,event_name text,path text,props jsonb NOT NULL DEFAULT '{}'::jsonb)")
            c.execute((ROOT/'supabase/migrations/20260926160000_proyecto_info_extra.sql').read_text())
            c.execute((ROOT/'supabase/migrations/20261017140000_regional_research.sql').read_text())
            c.execute((ROOT/'supabase/migrations/20261017160000_unify_regional_investigations.sql').read_text())

    @classmethod
    def tearDownClass(cls):cls.conn.close();cls.env.stop()

    def setUp(self):
        with self.conn,self.conn.cursor() as c:
            c.execute('TRUNCATE homes.proyecto CASCADE; TRUNCATE homes.asunto CASCADE; TRUNCATE public.homes_analytics_events')
            c.execute("INSERT INTO homes.proyecto(id,denominacion,municipio) VALUES ('p1','Plano 1','Municipio'),('p2','Plano 2','Municipio')")

    def sql(self,s,args=()):
        with self.conn,self.conn.cursor() as c:
            c.execute(s,args)
            return c.fetchall() if c.description else None

    def save(self,data=None,**kw):
        return r.save(data or payload(),request_id=kw.pop('request_id',str(uuid.uuid4())),unleased_test=True,**kw)

    def test_parent_ids_and_reuse_across_documents(self):
        self.save(payload('p1',True));self.save(payload('p2',True))
        self.assertEqual(self.sql('SELECT count(*) FROM homes.asunto'),[(3,)])
        self.assertEqual(self.sql('SELECT count(DISTINCT padre_id) FROM homes.asunto WHERE tipo=\'documento\''),[(1,)])
        self.assertEqual(self.sql("SELECT count(*) FROM homes.asunto_relacion WHERE tipo='pertenece_a'"),[(2,)])

    def test_unknown_is_persistent_and_not_repeated_until_requested(self):
        d=payload();d.update(asuntos=[],asunto_ref=None,estado='pendiente_identificar',tipo_entrada='tramite',razon_pendiente='Falta expediente concreto')
        self.save(d)
        self.assertEqual(self.sql('SELECT estado,razon_pendiente FROM homes.proyecto_investigacion_resumen'),[('pendiente_identificar','Falta expediente concreto')])
        c=r.claim('cursor');self.assertEqual(c['proyecto_id'],'p2')
        r.maintain('p2','cursor',c['token'],release=True)
        self.sql("UPDATE homes.proyecto_investigacion_actual SET revision_solicitada=true WHERE proyecto_id='p1'")
        self.assertEqual(r.claim('luna')['proyecto_id'],'p1')

    def test_changed_source_reopens_but_updated_at_alone_does_not(self):
        self.save()
        self.sql("UPDATE homes.proyecto SET updated_at=now() WHERE id='p1'")
        self.assertFalse(self.sql("SELECT fuente_cambiada FROM homes.proyecto_investigacion_resumen WHERE proyecto_id='p1'")[0][0])
        self.sql("UPDATE homes.proyecto SET denominacion='Plan actualizado' WHERE id='p1'")
        self.assertTrue(self.sql("SELECT fuente_cambiada FROM homes.proyecto_investigacion_resumen WHERE proyecto_id='p1'")[0][0])
        self.assertEqual(r.claim('cursor')['proyecto_id'],'p1')

    def test_cycle_rolls_back_nodes_and_snapshot(self):
        d=payload(document=True);d['asuntos'][0]['padre_ref']='doc'
        with self.assertRaises(psycopg2.Error):self.save(d)
        self.assertEqual(self.sql('SELECT count(*) FROM homes.asunto'),[(0,)])
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_investigacion'),[(0,)])

    def test_parent_change_rejected_and_no_partial_save(self):
        self.save(payload(document=True))
        d=payload(document=True)
        d['asuntos'][0]['clave_identidad']='oficial:municipio:PG-2'
        with self.assertRaisesRegex(ValueError,'contradictorio'):self.save(d)
        self.assertEqual(self.sql('SELECT count(*) FROM homes.asunto'),[(2,)])
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_investigacion'),[(1,)])

    def test_idempotence_and_changed_retry(self):
        key=str(uuid.uuid4());one=self.save(request_id=key)
        self.assertEqual(self.save(request_id=key),one)
        d=payload();d['resumen']+=' cambio'
        with self.assertRaises(ValueError):self.save(d,request_id=key)

    def test_leased_default_and_fencing(self):
        with self.assertRaisesRegex(ValueError,'obligatoria'):
            r.save(payload(),request_id=str(uuid.uuid4()))
        old=r.claim('cursor')
        self.sql("UPDATE homes.proyecto_investigacion_lease SET expires_at=clock_timestamp()-interval '1 second' WHERE proyecto_id='p1'")
        new=r.claim('luna')
        with self.assertRaises(ValueError):r.save(payload(),request_id=str(uuid.uuid4()),owner='cursor',token=old['token'])
        inv=r.save(payload(),request_id=str(uuid.uuid4()),owner='luna',token=new['token'],source_hash=new['source_hash'])
        self.assertEqual(self.sql('SELECT execution_mode FROM homes.proyecto_investigacion WHERE id=%s',(inv,)),[('leased',)])

    def test_source_change_during_research_cannot_be_marked_processed(self):
        lease=r.claim('luna')
        self.sql("UPDATE homes.proyecto SET denominacion='Cambio durante búsqueda' WHERE id='p1'")
        with self.assertRaisesRegex(ValueError,'cambió'):
            r.save(payload(),request_id=str(uuid.uuid4()),owner='luna',token=lease['token'],source_hash=lease['source_hash'])
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_investigacion'),[(0,)])

    def test_concurrent_claims_are_distinct(self):
        with ThreadPoolExecutor(8) as ex:
            results=list(ex.map(lambda i:r.claim('worker'+str(i)),range(8)))
        ids=[x['proyecto_id'] for x in results if x]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(set(ids),{'p1','p2'})

    def test_concurrent_documents_share_canonical_plan(self):
        with ThreadPoolExecutor(2) as ex:
            list(ex.map(lambda p:self.save(payload(p,True)),['p1','p2']))
        self.assertEqual(self.sql("SELECT count(*) FROM homes.asunto WHERE tipo='planeamiento'"),[(1,)])
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_investigacion_actual'),[(2,)])

    def test_possible_affects_relation_never_invents_parent(self):
        d=payload(document=True);d['asuntos'][1].pop('padre_ref')
        d['relaciones']=[{'origen_ref':'doc','destino_ref':'plan','tipo':'afecta_a','certeza':'posible','fuente_url':URL,'extracto':'Vínculo por comprobar'}]
        d['estado']='parcial';d['vinculos_pendientes']=[{'descripcion':'Verificar vínculo'}]
        self.save(d)
        self.assertEqual(self.sql('SELECT count(*) FROM homes.asunto WHERE padre_id IS NOT NULL'),[(0,)])
        self.assertEqual(self.sql('SELECT certeza FROM homes.asunto_relacion'),[('posible',)])

    def test_no_information_fallback_without_fake_sources_is_not_reselected(self):
        d=payload();d.update(asuntos=[],asunto_ref=None,estado='pendiente_identificar',
            tipo_entrada='pendiente',razon_pendiente='Fuentes inaccesibles',huecos='No se pudo abrir ni localizar contenido',
            fuentes=[],busquedas_intentadas=[{'consulta':'Sede oficial expediente','resultado':'inaccesible'}])
        self.save(d)
        self.assertEqual(self.sql("SELECT jsonb_array_length(fuentes),jsonb_array_length(busquedas_intentadas) FROM homes.proyecto_investigacion"),[(0,1)])
        self.assertEqual(r.claim('cursor')['proyecto_id'],'p2')

    def test_invalid_evidence_or_fake_complete_is_rejected(self):
        for change in ({'fuentes':[]},{'asunto_ref':None},{'vinculos_pendientes':[{'descripcion':'Falta padre'}]}):
            d=payload();d.update(change)
            with self.assertRaises(ValueError):self.save(d)
        self.assertEqual(self.sql('SELECT count(*) FROM homes.proyecto_investigacion'),[(0,)])


@unittest.skipUnless(os.getenv('TEST_REGIONAL_DB_URL'),'requires isolated PostgreSQL')
class RegionalMigrationTest(unittest.TestCase):
    def test_real_migration_preserves_legacy_and_imports_experimental_children(self):
        import hashlib
        from psycopg2.extras import Json
        url=os.environ['TEST_REGIONAL_DB_URL']
        with patch.dict(os.environ,{'SUPABASE_DB_URL':url}):
            conn=psycopg2.connect(url)
            try:
                with conn,conn.cursor() as c:
                    c.execute('DROP SCHEMA IF EXISTS homes CASCADE; CREATE SCHEMA homes')
                    for role in ('anon','authenticated','service_role'):
                        c.execute(f'DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$')
                    c.execute('''CREATE TABLE homes.proyecto(id text PRIMARY KEY,denominacion text,municipio text,
                      bocm_primary_id text,expediente_grupo text,raw_features_json jsonb,
                      num_viviendas_max int,metric_num_viviendas_max int,bocm_num_viviendas_max int,
                      sup_total_m2 float,metric_sup_total_m2 float,bocm_sup_total_m2 float,updated_at timestamptz)''')
                    c.execute('DROP TABLE IF EXISTS public.homes_analytics_events CASCADE')
                    c.execute("CREATE TABLE public.homes_analytics_events(session_id uuid,page_id uuid,event_name text,path text,props jsonb NOT NULL DEFAULT '{}'::jsonb)")
                    c.execute((ROOT/'supabase/migrations/20260926160000_proyecto_info_extra.sql').read_text())
                    c.execute("INSERT INTO homes.proyecto(id) VALUES ('old'),('document'),('unknown')")
                    c.execute("INSERT INTO homes.proyecto_investigacion(proyecto_id,estado,resumen) VALUES ('old','completa','Legacy untouched') RETURNING id")
                    old_id=c.fetchone()[0]
                    c.execute((ROOT/'supabase/migrations/20261017120000_research_leases.sql').read_text())
                    c.execute((ROOT/'supabase/migrations/20261017140000_regional_research.sql').read_text())
                    plan,doc=str(uuid.uuid4()),str(uuid.uuid4())
                    c.execute("INSERT INTO homes.asunto(id,clave_identidad,tipo,titulo,fuente_url,extracto) VALUES (%s,'plan','planeamiento','Plan',%s,'Plan')",(plan,URL))
                    c.execute("INSERT INTO homes.asunto(id,clave_identidad,tipo,titulo,padre_id,fuente_url,extracto) VALUES (%s,'doc','documento','Plano',%s,%s,'Plano del plan')",(doc,plan,URL))
                    request=str(uuid.uuid4())
                    data=payload('document',True)
                    data['datos']=[{'bloque':'identificacion','etiqueta':'Identidad','valor':'Contexto',
                        'confianza':'alta','fuente_tipo':'registro_contexto','fuente_url':URL},
                        {'bloque':'contenido','etiqueta':'Contenido','valor':'Normas',
                         'confianza':'alta','fuente_tipo':'oficial','fuente_url':URL}]
                    digest=hashlib.sha256(__import__('json').dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                    c.execute('''INSERT INTO homes.entrada_investigacion(request_id,proyecto_id,tipo_entrada,asunto_id,
                      estado,resumen,fuentes,busquedas_intentadas,datos,hallazgos,vinculos_pendientes,payload,
                      payload_sha256,source_hash,execution_mode)
                      VALUES (%s,'document','documento',%s,'parcial',%s,'[]','[]',%s,'[]','[]',%s,%s,homes.research_entrada_source_hash((SELECT to_jsonb(p) FROM homes.proyecto p WHERE id='document')),'unleased_test') RETURNING id''',
                      (request,doc,data['resumen'],Json(data['datos']),Json(data),digest))
                    experimental_id=c.fetchone()[0]
                    c.execute("INSERT INTO homes.entrada_investigacion_actual VALUES ('document',%s,false)",(experimental_id,))
                    c.execute("INSERT INTO homes.asunto_relacion VALUES (%s,%s,'pertenece_a','confirmada',%s,'Plano del plan',%s)",(doc,plan,URL,experimental_id))
                    c.execute((ROOT/'supabase/migrations/20261017160000_unify_regional_investigations.sql').read_text())
                    c.execute("SELECT id,resumen FROM homes.proyecto_investigacion WHERE proyecto_id='old'")
                    self.assertEqual(c.fetchone(),(old_id,'Legacy untouched'))
                    c.execute('SELECT id,payload FROM homes.proyecto_investigacion WHERE entrada_legacy_id=%s',(experimental_id,))
                    migrated_id,stored=c.fetchone();self.assertEqual(stored,data)
                    c.execute('SELECT investigacion_id FROM homes.asunto_relacion')
                    self.assertEqual(c.fetchone()[0],migrated_id)
                    c.execute('SELECT bloque,publicable,raw_json FROM homes.proyecto_dato_extra WHERE investigacion_id=%s ORDER BY orden',(migrated_id,))
                    converted=c.fetchall()
                    self.assertEqual([(x[0],x[1]) for x in converted],[('situacion',False),('programa',True)])
                    self.assertEqual(converted[0][2],data['datos'][0])
                    c.execute("SELECT public.get_proyecto_info_extra('document')->>'estado'")
                    self.assertEqual(c.fetchone()[0],'parcial')
                    c.execute("SELECT to_regclass('homes.entrada_investigacion')")
                    self.assertIsNone(c.fetchone()[0])
                    c.execute("SELECT has_column_privilege('anon','homes.proyecto_investigacion','payload','SELECT'),has_column_privilege('anon','homes.proyecto_dato_extra','raw_json','SELECT')")
                    self.assertEqual(c.fetchone(),(False,False))
                # The original public writer entry point also handles modern payloads/leases.
                from save_proyecto_info_extra import save as common_save
                lease=r.claim('cursor-modern')
                self.assertEqual(lease['proyecto_id'],'unknown')
                modern_id=common_save(payload('unknown'),owner=lease['owner'],token=lease['token'],
                    request_id=str(uuid.uuid4()),source_hash=lease['source_hash'])
                with conn,conn.cursor() as c:
                    c.execute('SELECT execution_mode FROM homes.proyecto_investigacion WHERE id=%s',(modern_id,))
                    self.assertEqual(c.fetchone()[0],'leased')
                # Identical historical retries resolve to the unified ID, without schema coercion.
                self.assertEqual(r.save(data,request_id=request,unleased_test=True),migrated_id)
                with self.assertRaises(psycopg2.Error):
                    with conn,conn.cursor() as c:c.execute("DELETE FROM homes.entrada_investigacion_archivo_20261017")
            finally:conn.close()


class PromptContractTest(unittest.TestCase):
    def test_user_research_sections_and_original_json_fields_are_preserved(self):
        import hashlib,json,re
        prompt=(ROOT/'.cursor/prompts/investigar-proyecto.md').read_text()
        core=prompt[prompt.index('2. Investigar'):prompt.index('6. Guardar')]
        self.assertEqual(hashlib.sha256(re.sub(r'\s+',' ',core).strip().encode()).hexdigest(),
                         '7cf0ce54993f12bdb7cf4ac7a856f8f045f8794cbb1fa79597d091d9cb599af9')
        sample=json.loads(prompt.split('```json\n',1)[1].split('```',1)[0])
        self.assertTrue({'proyecto_id','estado','resumen','huecos','datos','hallazgos'}<=sample.keys())
        self.assertIn('python3 db/save_proyecto_info_extra.py --file',prompt)
        self.assertIn('--request-id',prompt)


if __name__=='__main__':unittest.main()
