#!/usr/bin/env python3
"""Shared Cursor/Luna lease client. All transactions lock proyecto before lease."""
import argparse
import json
import uuid
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from save_proyecto_info_extra import _db_url


@contextmanager
def connection():
    # 8s, not 15s: a runaway investigación query must release the tiny
    # instance before it queues the public RPCs (anon timeout is 3s).
    conn = psycopg2.connect(_db_url(), connect_timeout=10,
                            options='-c statement_timeout=8000 -c lock_timeout=3000')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def claim(owner, ttl=600):
    if not owner or not 60 <= ttl <= 3600:
        raise ValueError('owner requerido; ttl entre 60 y 3600 segundos')
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # SKIP LOCKED avoids both a concurrent reservation and a concurrent commit.
        cur.execute('''SELECT p.* FROM homes.proyecto p
          LEFT JOIN homes.research_human_project_visits v ON v.proyecto_id=p.id
          WHERE NOT EXISTS (SELECT 1 FROM homes.proyecto_investigacion i WHERE i.proyecto_id=p.id)
            AND NOT EXISTS (SELECT 1 FROM homes.proyecto_investigacion_lease l
                WHERE l.proyecto_id=p.id AND (l.expires_at > clock_timestamp()
                   OR l.retry_after > clock_timestamp()))
          ORDER BY (coalesce(v.human_sessions,0)>0) DESC, COALESCE(p.num_viviendas_max,p.metric_num_viviendas_max,p.bocm_num_viviendas_max,0) DESC,
                   COALESCE(p.sup_total_m2,p.metric_sup_total_m2,p.bocm_sup_total_m2,0) DESC,
                   p.updated_at DESC NULLS LAST, p.id
          LIMIT 1 FOR UPDATE OF p SKIP LOCKED''')
        project = cur.fetchone()
        if project is None:
            return None
        # New statement => fresh READ COMMITTED snapshot after taking project lock.
        cur.execute("""SELECT EXISTS (SELECT 1 FROM homes.proyecto_investigacion WHERE proyecto_id=%s)
                     OR EXISTS (SELECT 1 FROM homes.proyecto_investigacion_lease WHERE proyecto_id=%s
                       AND (expires_at>clock_timestamp() OR retry_after>clock_timestamp())) AS busy""",
                    (project['id'], project['id']))
        if cur.fetchone()['busy']:
            return None  # a concurrent claimant won; safe to retry in a later run
        token = str(uuid.uuid4())
        cur.execute('''INSERT INTO homes.proyecto_investigacion_lease (proyecto_id,owner,token,expires_at)
          VALUES (%s,%s,%s,clock_timestamp()+%s*interval '1 second')
          ON CONFLICT (proyecto_id) DO UPDATE SET owner=EXCLUDED.owner, token=EXCLUDED.token,
            expires_at=EXCLUDED.expires_at, retry_after=NULL, skip_reason=NULL,
            investigacion_id=NULL,payload_sha256=NULL
          RETURNING expires_at''', (project['id'], owner, token, ttl))
        return {'proyecto_id': project['id'], 'owner': owner, 'token': token,
                'expires_at': cur.fetchone()['expires_at'], 'project': dict(project)}


def maintain(project_id, owner, token, ttl=600, release=False, skip_reason=None):
    if not 60 <= ttl <= 3600:
        raise ValueError('ttl entre 60 y 3600')
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM homes.proyecto WHERE id=%s FOR UPDATE', (project_id,))
        cur.execute('''UPDATE homes.proyecto_investigacion_lease SET
            expires_at=CASE WHEN %s THEN clock_timestamp() ELSE clock_timestamp()+%s*interval '1 second' END,
            retry_after=CASE WHEN %s IS NOT NULL THEN clock_timestamp()+interval '24 hours' ELSE NULL END,
            skip_reason=%s
          WHERE proyecto_id=%s AND owner=%s AND token=%s AND expires_at>clock_timestamp()
            AND investigacion_id IS NULL RETURNING proyecto_id''',
                    (release, ttl, skip_reason, skip_reason, project_id, owner, token))
        if not cur.fetchone():
            raise RuntimeError('Reserva perdida, caducada o ya completada')


def context(project_id):
    """Complete related rows; avoid truncation of the research starting material."""
    from psycopg2 import sql
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT table_name FROM information_schema.columns
                       WHERE table_schema='homes' AND column_name='proyecto_id'
                         AND table_name IN ('proyecto_tramite','proyecto_documento','proyecto_bocm_publicacion','proyecto_pdf_metric')''')
        tables = [r['table_name'] for r in cur.fetchall()]
        result = {}
        for table in tables:
            cur.execute(sql.SQL('SELECT * FROM homes.{} WHERE proyecto_id=%s').format(sql.Identifier(table)),
                        (project_id,))
            result[table] = [dict(r) for r in cur.fetchall()]
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['claim', 'renew', 'release', 'skip', 'context'])
    p.add_argument('--owner', required=True)
    p.add_argument('--project')
    p.add_argument('--token')
    p.add_argument('--ttl', type=int, default=600)
    p.add_argument('--reason')
    a = p.parse_args()
    if a.action == 'claim':
        result = claim(a.owner, a.ttl)
    elif a.action == 'context':
        if not a.project:
            p.error('--project requerido')
        result = context(a.project)
    else:
        if not a.project or not a.token or (a.action == 'skip' and not a.reason):
            p.error('--project, --token y --reason (para skip) requeridos')
        maintain(a.project, a.owner, a.token, a.ttl, release=a.action != 'renew',
                 skip_reason=a.reason if a.action == 'skip' else None)
        result = {'ok': True}
    print(json.dumps(result, default=str, ensure_ascii=False))


if __name__ == '__main__':
    main()
