#!/usr/bin/env python3
"""Investigate every regional entry, preserving canonical identities and evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import uuid
from urllib.parse import urlparse
from datetime import date

from psycopg2.extras import Json, RealDictCursor
from research_lease import connection, context as legacy_context

TIPOS={'actuacion','planeamiento','norma','subasta','expediente','documento','otro'}
ENTRADAS={'actuacion','planeamiento','modificacion_normativa','documento','subasta','tramite','anuncio','pendiente'}
ESTADOS={'completa','parcial','pendiente_identificar'}
RELACIONES={'pertenece_a','modifica','afecta_a','describe','vinculado_a'}


def source(cur,project):
    cur.execute('SELECT homes.research_entrada_source_hash(to_jsonb(p)) FROM homes.proyecto p WHERE id=%s',(project,))
    row=cur.fetchone()
    if row is None:raise ValueError('Entrada no existe')
    return row[0]


def evidence(row):
    url=urlparse(row.get('fuente_url') or row.get('url') or '')
    if url.scheme not in ('https','http') or not url.netloc or not row.get('extracto'):
        raise ValueError('Falta URL y extracto verificable')
    if row.get('fecha'):date.fromisoformat(row['fecha'])


def validate(data):
    if not data.get('proyecto_id') or data.get('tipo_entrada') not in ENTRADAS or data.get('estado') not in ESTADOS:
        raise ValueError('Identidad/tipo/estado inválido')
    if not isinstance(data.get('resumen'),str) or len(data['resumen'].strip())<400:
        raise ValueError('Se requiere relato completo, también para casos pendientes')
    for key in ('datos','hallazgos','vinculos_pendientes','busquedas_intentadas','relaciones'):
        if not isinstance(data.get(key,[]),list):raise ValueError(f'{key} debe ser lista')
    from save_proyecto_info_extra import BLOQUES, CONFIANZA, FUENTE
    for fact in data.get('datos',[]):
        if (not isinstance(fact,dict) or fact.get('bloque') not in BLOQUES
            or fact.get('confianza') not in CONFIANZA or fact.get('fuente_tipo') not in FUENTE
            or not fact.get('etiqueta') or not fact.get('valor')):
            raise ValueError('Dato incompatible con proyecto_dato_extra')
        if fact.get('fuente_fecha'):date.fromisoformat(fact['fuente_fecha'])
    for finding in data.get('hallazgos',[]):
        if not isinstance(finding,dict) or not finding.get('titulo') or not finding.get('cuerpo'):
            raise ValueError('Hallazgo incompatible con proyecto_hallazgo')
    nodes=data.get('asuntos')
    if not isinstance(nodes,list):raise ValueError('asuntos debe ser lista')
    refs={n.get('ref') for n in nodes}
    if len(refs)!=len(nodes) or None in refs:raise ValueError('refs duplicadas o ausentes')
    if data.get('asunto_ref') not in refs:
        if data.get('asunto_ref') is not None or data['estado']!='pendiente_identificar' or not data.get('razon_pendiente'):
            raise ValueError('Sin asunto: pendiente_identificar y motivo obligatorios')
    if data['estado']=='completa' and data.get('vinculos_pendientes'):
        raise ValueError('Vínculos pendientes requieren estado parcial')
    for n in nodes:
        if n.get('tipo') not in TIPOS or not n.get('clave_identidad') or not n.get('titulo'):
            raise ValueError('Asunto sin identidad/tipo/título')
        if n.get('padre_ref') and n['padre_ref'] not in refs:raise ValueError('Padre desconocido')
        evidence(n)
    if not isinstance(data.get('fuentes'),list):raise ValueError('fuentes debe ser lista')
    if not data['fuentes']:
        if data['estado']=='completa' or not data.get('busquedas_intentadas') or not data.get('huecos'):
            raise ValueError('Sin fuentes: fallback con búsquedas intentadas y huecos obligatorio')
    for attempt in data.get('busquedas_intentadas',[]):
        if not isinstance(attempt,dict) or not attempt.get('consulta') or not attempt.get('resultado'):
            raise ValueError('Búsqueda intentada sin consulta/resultado')
    for f in data['fuentes']:evidence(f)
    for r in data.get('relaciones',[]):
        if r.get('origen_ref') not in refs or r.get('destino_ref') not in refs or r.get('tipo') not in RELACIONES:
            raise ValueError('Relación inválida')
        if r.get('certeza') not in ('confirmada','posible'):raise ValueError('Certeza inválida')
        if r['tipo']=='pertenece_a':
            origin=next(n for n in nodes if n['ref']==r['origen_ref'])
            if r['certeza']!='confirmada' or origin.get('padre_ref')!=r['destino_ref']:
                raise ValueError('Pertenencia debe coincidir con padre_ref confirmado')
        evidence(r)


def context(project):
    with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT p.*,homes.research_entrada_source_hash(to_jsonb(p)) AS _research_source_hash FROM homes.proyecto p WHERE id=%s',(project,))
        row=cur.fetchone()
        if row is None:raise ValueError('Entrada no existe')
        fingerprint=row.pop('_research_source_hash')
        cur.execute('SELECT * FROM homes.asunto WHERE municipio=%s ORDER BY clave_identidad',(row.get('municipio'),))
        topics=[dict(x) for x in cur.fetchall()]
        cur.execute('SELECT * FROM homes.proyecto_investigacion_resumen WHERE proyecto_id=%s',(project,))
        previous=cur.fetchone()
    return {'source_hash':fingerprint,'project':dict(row),'related':legacy_context(project),'asuntos_existentes':topics,
            'investigacion_anterior':dict(previous) if previous else None}


def claim(owner,ttl=600):
    if not owner or not 60<=ttl<=3600:raise ValueError('owner/ttl inválido')
    with connection() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT p.* FROM homes.proyecto p
          LEFT JOIN homes.research_human_project_visits v ON v.proyecto_id=p.id
          LEFT JOIN homes.proyecto_investigacion_actual c ON c.proyecto_id=p.id
          LEFT JOIN homes.proyecto_investigacion i ON i.id=c.investigacion_id
          WHERE (c.proyecto_id IS NULL OR c.revision_solicitada OR
                 i.source_hash IS DISTINCT FROM homes.research_entrada_source_hash(to_jsonb(p)))
            AND NOT EXISTS(SELECT 1 FROM homes.proyecto_investigacion_lease l
              WHERE l.proyecto_id=p.id AND l.expires_at>clock_timestamp())
          ORDER BY (coalesce(v.human_sessions,0)>0) DESC,
            COALESCE(p.num_viviendas_max,p.metric_num_viviendas_max,p.bocm_num_viviendas_max,0) DESC,
            COALESCE(p.sup_total_m2,p.metric_sup_total_m2,p.bocm_sup_total_m2,0) DESC,
            p.updated_at DESC NULLS LAST,p.id LIMIT 1 FOR UPDATE OF p SKIP LOCKED''')
        p=cur.fetchone()
        if p is None:return None
        # A fresh snapshot after obtaining the project lock fences a just-committed claimant/save.
        cur.execute('''SELECT EXISTS(SELECT 1 FROM homes.proyecto_investigacion_lease
             WHERE proyecto_id=%s AND expires_at>clock_timestamp()) AS busy,
             EXISTS(SELECT 1 FROM homes.proyecto_investigacion_actual c
               JOIN homes.proyecto_investigacion i ON i.id=c.investigacion_id
               JOIN homes.proyecto p ON p.id=c.proyecto_id WHERE p.id=%s
               AND NOT c.revision_solicitada AND i.source_hash=homes.research_entrada_source_hash(to_jsonb(p))) AS done''',(p['id'],p['id']))
        checks=cur.fetchone()
        if checks['busy'] or checks['done']:return None
        token=str(uuid.uuid4())
        cur.execute('SELECT homes.research_entrada_source_hash(to_jsonb(p)) AS h FROM homes.proyecto p WHERE id=%s',(p['id'],))
        fingerprint=cur.fetchone()['h']
        cur.execute('''INSERT INTO homes.proyecto_investigacion_lease(proyecto_id,owner,token,expires_at) VALUES (%s,%s,%s,clock_timestamp()+%s*interval '1 second')
          ON CONFLICT(proyecto_id) DO UPDATE SET owner=EXCLUDED.owner,token=EXCLUDED.token,expires_at=EXCLUDED.expires_at,investigacion_id=NULL,payload_sha256=NULL,retry_after=NULL,skip_reason=NULL''',(p['id'],owner,token,ttl))
        return {'proyecto_id':p['id'],'owner':owner,'token':token,'source_hash':fingerprint,'project':dict(p)}


def maintain(project,owner,token,ttl=600,release=False):
    if not 60<=ttl<=3600:raise ValueError('ttl inválido')
    with connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT id FROM homes.proyecto WHERE id=%s FOR UPDATE',(project,))
        cur.execute('''UPDATE homes.proyecto_investigacion_lease SET expires_at=clock_timestamp()+%s*interval '1 second'
          WHERE proyecto_id=%s AND owner=%s AND token=%s AND expires_at>clock_timestamp() RETURNING proyecto_id''',
          (0 if release else ttl,project,owner,token))
        if not cur.fetchone():raise ValueError('Reserva perdida o caducada')


def save(data,*,request_id,owner=None,token=None,unleased_test=False,source_hash=None):
    request_id=str(uuid.UUID(request_id))
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    with connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT id FROM homes.proyecto WHERE id=%s FOR UPDATE',(data['proyecto_id'],))
        fingerprint=source(cur,data['proyecto_id'])
        cur.execute('SELECT id,payload_sha256 FROM homes.proyecto_investigacion WHERE request_id=%s',(request_id,))
        prior=cur.fetchone()
        if prior:
            if prior[1]!=digest:raise ValueError('Reintento con contenido distinto')
            return prior[0]
        validate(data)
        if not unleased_test:
            cur.execute('''SELECT 1 FROM homes.proyecto_investigacion_lease WHERE proyecto_id=%s AND owner=%s
              AND token=%s AND expires_at>clock_timestamp() FOR UPDATE''',(data['proyecto_id'],owner,token))
            if not cur.fetchone():raise ValueError('Reserva viva obligatoria')
            if source_hash is None:raise ValueError('source_hash del contexto obligatorio')
        if source_hash is not None and fingerprint!=source_hash:
            raise ValueError('La fuente cambió durante la investigación; conservar resultado y revisar')
        cur.execute('SELECT pg_advisory_xact_lock(17140000)')
        ids={}
        for n in sorted(data['asuntos'],key=lambda n:n['clave_identidad']):
            node_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'homes:asunto:'+n['clave_identidad']))
            cur.execute('''INSERT INTO homes.asunto(id,clave_identidad,tipo,titulo,municipio,fuente_url,extracto)
              VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(clave_identidad) DO NOTHING''',
              (node_id,n['clave_identidad'],n['tipo'],n['titulo'],n.get('municipio'),n['fuente_url'],n['extracto']))
            cur.execute('SELECT id::text,tipo FROM homes.asunto WHERE clave_identidad=%s',(n['clave_identidad'],))
            row=cur.fetchone()
            if row[1]!=n['tipo']:raise ValueError('La identidad existente tiene otro tipo; revisar')
            ids[n['ref']]=row[0]
        for n in data['asuntos']:
            if n.get('padre_ref'):
                child,parent=ids[n['ref']],ids[n['padre_ref']]
                cur.execute('SELECT padre_id::text FROM homes.asunto WHERE id=%s',(child,))
                old=cur.fetchone()[0]
                if old and old!=parent:raise ValueError('Padre confirmado contradictorio')
                cur.execute('UPDATE homes.asunto SET padre_id=%s WHERE id=%s',(parent,child))
        cur.execute("SELECT set_config('homes.research_owner',%s,true),set_config('homes.research_token',%s,true),set_config('homes.research_unleased_test',%s,true)",
                    (owner or '',token or '','on' if unleased_test else 'off'))
        cur.execute('''INSERT INTO homes.proyecto_investigacion(request_id,proyecto_id,tipo_entrada,asunto_id,
          estado,resumen,huecos,razon_pendiente,fuentes,busquedas_intentadas,vinculos_pendientes,payload,
          payload_sha256,source_hash,execution_mode)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
          (request_id,data['proyecto_id'],data['tipo_entrada'],ids.get(data.get('asunto_ref')),data['estado'],
           data['resumen'],data.get('huecos'),data.get('razon_pendiente'),Json(data['fuentes']),
           Json(data.get('busquedas_intentadas',[])),Json(data.get('vinculos_pendientes',[])),
           Json(data),digest,fingerprint,'unleased_test' if unleased_test else 'leased'))
        inv=cur.fetchone()[0]
        cur.execute('SELECT homes.research_insert_children(%s,%s,%s,%s)',
                    (inv,data['proyecto_id'],Json(data.get('datos',[])),Json(data.get('hallazgos',[]))))
        relations=list(data.get('relaciones',[]))
        for n in data['asuntos']:
            if n.get('padre_ref'):
                relations.append({'origen_ref':n['ref'],'destino_ref':n['padre_ref'],'tipo':'pertenece_a',
                                  'certeza':'confirmada','fuente_url':n['fuente_url'],'extracto':n['extracto']})
        for r in relations:
            cur.execute('''INSERT INTO homes.asunto_relacion VALUES (%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT DO NOTHING''',(ids[r['origen_ref']],ids[r['destino_ref']],r['tipo'],r['certeza'],r['fuente_url'],r['extracto'],inv))
        cur.execute('''INSERT INTO homes.proyecto_investigacion_actual(proyecto_id,investigacion_id)
          VALUES (%s,%s) ON CONFLICT(proyecto_id) DO UPDATE SET investigacion_id=EXCLUDED.investigacion_id,revision_solicitada=false''',(data['proyecto_id'],inv))
        if not unleased_test:
            cur.execute('''UPDATE homes.proyecto_investigacion_lease SET expires_at=clock_timestamp(),investigacion_id=%s,payload_sha256=%s
              WHERE proyecto_id=%s AND owner=%s AND token=%s AND expires_at>clock_timestamp() RETURNING proyecto_id''',
              (inv,digest,data['proyecto_id'],owner,token))
            if not cur.fetchone():raise ValueError('Reserva caducada durante guardado')
        return inv


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['claim','context','renew','release','save','review'])
    p.add_argument('--owner');p.add_argument('--token');p.add_argument('--project');p.add_argument('--file')
    p.add_argument('--request-id');p.add_argument('--source-hash');p.add_argument('--ttl',type=int,default=600)
    a=p.parse_args()
    if a.action=='claim':out=claim(a.owner,a.ttl)
    elif a.action=='context':out=context(a.project)
    elif a.action=='save':
        if not a.file or not a.request_id or not a.source_hash:p.error('--file, --request-id y --source-hash obligatorios')
        out={'investigacion_id':save(json.loads(Path(a.file).read_text()),request_id=a.request_id,owner=a.owner,token=a.token,source_hash=a.source_hash)}
    elif a.action=='review':
        with connection() as conn,conn.cursor() as cur:
            cur.execute('UPDATE homes.proyecto_investigacion_actual SET revision_solicitada=true WHERE proyecto_id=%s RETURNING proyecto_id',(a.project,))
            out={'revision_solicitada':cur.fetchone() is not None}
    else:maintain(a.project,a.owner,a.token,a.ttl,release=a.action=='release');out={'ok':True}
    print(json.dumps(out,default=str,ensure_ascii=False))


if __name__=='__main__':main()
