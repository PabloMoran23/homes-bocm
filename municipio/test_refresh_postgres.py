"""Optional real PostgreSQL test: isolated local schema only."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from municipio.refresh_queue import DDL, Queue


@unittest.skipUnless(os.environ.get('REVIEW_TEST_DSN'), 'local PostgreSQL DSN not supplied')
class PostgresQueueTest(unittest.TestCase):
    def test_atomic_claim_restart_and_fencing(self):
        import psycopg2
        dsn=os.environ['REVIEW_TEST_DSN']
        parsed=urlparse(dsn)
        self.assertIn(parsed.hostname,('localhost','127.0.0.1'))
        self.assertEqual(parsed.path,'/review_test_856')
        schema='test_'+uuid.uuid4().hex
        def connection():
            conn=psycopg2.connect(dsn)
            with conn.cursor() as cur:
                cur.execute(f'SET search_path TO {schema}')
            conn.commit()
            return conn
        admin=psycopg2.connect(dsn)
        try:
            with admin.cursor() as cur:
                cur.execute(f'CREATE SCHEMA {schema}')
            admin.commit()
            conn=connection()
            with conn.cursor() as cur:
                cur.execute(DDL)
                cur.execute(DDL)
            conn.commit()
            q=Queue(conn)
            q.reconcile([dict(slug='one',host='one.test',hash='v1',interval=15*86400)],1000)
            def claim():
                worker=connection()
                try:
                    return Queue(worker).claim(1000)
                finally:
                    worker.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                claimed=list(pool.map(lambda _:claim(),range(2)))
            self.assertEqual(sum(x is not None for x in claimed),1)
            old=next(x for x in claimed if x)
            conn.close()
            conn=connection()
            q=Queue(conn)
            new=q.claim(1900)
            self.assertIsNotNone(new)
            self.assertFalse(q.finish(old,1901,complete=True))
            self.assertTrue(q.finish(new,1902,complete=True))
            self.assertFalse(q.finish(new,1903,complete=True))
            self.assertEqual(q.metrics(1904)['complete_last_24h'],1)
            q.checkpoint_metrics(1904,q.metrics(1904))
            conn.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
            admin.commit()
            admin.close()

    def test_stale_staged_worker_cannot_publish_but_current_worker_commits_atomically(self):
        import psycopg2
        import tempfile
        import time
        from pathlib import Path
        from unittest.mock import patch
        from municipio.manifest import load_manifest
        from municipio.refresh_dispatch import review
        from municipio.orchestrator import RUNNERS, run as real_run
        from ingest import IngestSession, sync_municipio_output as real_sync
        dsn=os.environ['REVIEW_TEST_DSN']
        parsed=urlparse(dsn)
        self.assertIn(parsed.hostname,('localhost','127.0.0.1'))
        self.assertEqual(parsed.path,'/review_test_856')
        schema='test_'+uuid.uuid4().hex
        admin=psycopg2.connect(dsn)
        def connection():
            conn=psycopg2.connect(dsn)
            with conn.cursor() as cur:
                cur.execute(f'SET search_path TO {schema}')
            conn.commit()
            return conn
        try:
            with admin.cursor() as cur:
                cur.execute(f'CREATE SCHEMA {schema}')
            admin.commit()
            conn=connection()
            with conn.cursor() as cur:
                cur.execute(DDL)
                cur.execute('CREATE TABLE canonical_test(payload TEXT)')
                cur.execute('CREATE TABLE ingest_test(stage TEXT)')
                cur.execute('CREATE TABLE municipio(slug TEXT PRIMARY KEY,last_ingest_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)')
                cur.execute("INSERT INTO municipio VALUES('oviedo', now(), now())")
            conn.commit()
            q=Queue(conn)
            now=time.time()
            source=dict(slug='oviedo',host='one.test',hash='v1',interval=15*86400)
            q.reconcile([source],now)
            old=q.claim(now)
            # A different connection revokes the lease after capture started.
            other=connection()
            source['hash']='v2'
            Queue(other).reconcile([source],now+.01)
            current=Queue(other).claim(now+.02)
            other.close()
            captured=[]
            def capture(manifest):
                (manifest.output_dir/'proyectos.jsonl').write_text('{"id":"valid-stage"}\n')
                captured.append(manifest.output_dir)
                return {'review_complete':True}
            def start(*args,conn,**kwargs):
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO ingest_test VALUES('start')")
                return 1
            def end(*args,conn,**kwargs):
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO ingest_test VALUES('finish')")
            def save_projects(rows, *, conn):
                with conn.cursor() as cur:
                    for row in rows:
                        cur.execute('INSERT INTO canonical_test VALUES(%s)',(row['id'],))
                return len(rows)
            def publisher(slug,*,conn,manifest):
                # The real sync + IngestSession use this same connection. Only
                # table mappers are substituted for the isolated canonical table.
                with patch('ingest.available',return_value=True), patch('ingest.portal_proyecto_row',side_effect=lambda rec,**kw:dict(rec)), patch('ingest.save_municipio_from_manifest',return_value=slug), patch('ingest.save_proyectos',side_effect=save_projects), patch('ingest.save_inmuebles',return_value={}), patch('ingest.save_licencias',return_value=0), patch('ingest.save_documentos',return_value=0), patch('ingest.touch_last_ingest_at'):
                    return real_sync(slug,conn=conn,manifest=manifest)
            with tempfile.TemporaryDirectory() as tmp:
                manifest=load_manifest('oviedo')
                manifest._output_dir=Path(tmp)/'canonical-output'
                manifest.output_dir.mkdir()
                original=manifest.output_dir/'proyectos.jsonl'
                original.write_text('original')
                manifest.proyectos.enabled=True
                manifest.licencias.enabled=False
                with patch('municipio.refresh_dispatch.load_manifest',return_value=manifest), patch('municipio.proyectos_runner.update',side_effect=capture), patch('municipio.orchestrator.run',return_value={'steps':{}}), patch('municipio.refresh_dispatch._publication_connection',side_effect=connection), patch('ingest.sync_municipio_output',side_effect=publisher), patch('ingest.start_ingest_run',side_effect=start), patch('ingest.finish_ingest_run',side_effect=end):
                    # Exercise real orchestrator timeout + real legacy deferral
                    # helpers, redirected to this isolated PostgreSQL schema.
                    # Any staging deferral regression would clear this mark.
                    with conn.cursor() as cur:
                        cur.execute("SELECT last_ingest_at FROM municipio WHERE slug='oviedo'")
                        freshness=cur.fetchone()[0]
                    conn.commit()
                    with patch('municipio.orchestrator.run',side_effect=real_run), patch.dict(RUNNERS,{'enrich_geometry':lambda manifest: (_ for _ in ()).throw(TimeoutError('staging source timeout'))}), patch('ingest.connect',side_effect=connection), patch('ingest.SCHEMA',schema), patch.dict(os.environ,{'DATABASE_URL':dsn}):
                        stale_timeout=review(old)
                        self.assertFalse(stale_timeout['complete'])
                        self.assertIn('TimeoutError',stale_timeout['error'])
                        self.assertFalse(q.finish(old,time.time(),**stale_timeout))
                        with conn.cursor() as cur:
                            cur.execute('SELECT lease_token FROM refresh_review')
                            self.assertEqual(cur.fetchone()[0],current['token'])
                            cur.execute("SELECT last_ingest_at FROM municipio WHERE slug='oviedo'")
                            self.assertEqual(cur.fetchone()[0],freshness)
                        conn.commit()
                        current_timeout=review(current)
                        self.assertFalse(current_timeout['complete'])
                        self.assertTrue(q.finish(current,time.time(),**current_timeout))
                    with conn.cursor() as cur:
                        cur.execute("SELECT last_ingest_at FROM municipio WHERE slug='oviedo'")
                        self.assertEqual(cur.fetchone()[0],freshness)
                        cur.execute('SELECT count(*) FROM canonical_test')
                        self.assertEqual(cur.fetchone()[0],0)
                        cur.execute('SELECT count(*) FROM ingest_test')
                        self.assertEqual(cur.fetchone()[0],0)
                        cur.execute('SELECT failures,retry_at,last_error FROM refresh_review')
                        failures,retry_at,error=cur.fetchone()
                        self.assertEqual(failures,1)
                        self.assertGreater(retry_at,time.time())
                        self.assertIn('TimeoutError',error)
                    conn.commit()
                    # Requeue using a new configuration after the valid retry;
                    # the revoked original token remains revoked.
                    source['hash']='v2-after-timeout'
                    q.reconcile([source],time.time())
                    current=q.claim(time.time())
                    captured.clear()
                    stale=review(old)
                    self.assertFalse(stale['complete'])
                    self.assertIn('StaleLease',stale['error'])
                    self.assertEqual(len(captured),1)  # Valid staging already exists.
                    self.assertNotEqual(captured[0],manifest.output_dir)
                    with conn.cursor() as cur:
                        cur.execute('SELECT count(*) FROM canonical_test')
                        self.assertEqual(cur.fetchone()[0],0)
                        cur.execute('SELECT count(*) FROM ingest_test')
                        self.assertEqual(cur.fetchone()[0],0)
                        cur.execute('SELECT lease_token FROM refresh_review')
                        self.assertEqual(cur.fetchone()[0],current['token'])
                    conn.commit()
                    self.assertEqual(original.read_text(),'original')
                    success=review(current)
                    self.assertTrue(success['complete'])
                    with conn.cursor() as cur:
                        cur.execute('SELECT count(*) FROM canonical_test')
                        self.assertEqual(cur.fetchone()[0],1)
                        cur.execute('SELECT count(*) FROM ingest_test')
                        self.assertEqual(cur.fetchone()[0],2)
                        cur.execute('SELECT lease_token,last_write,last_complete FROM refresh_review')
                        token,written,completed=cur.fetchone()
                        self.assertIsNone(token)
                        self.assertEqual(written,completed)
                    conn.commit()
                    repeated=review(current)
                    self.assertFalse(repeated['complete'])
                    with conn.cursor() as cur:
                        cur.execute('SELECT count(*) FROM canonical_test')
                        self.assertEqual(cur.fetchone()[0],1)
                    conn.commit()
                    self.assertEqual(original.read_text(),'original')
            # Expiry during the callback rolls back both canonical writes and
            # session history, even after IngestSession.__exit__ has run.
            source['hash']='v3'
            source['slug']='expiry-test'
            q.reconcile([source],time.time())
            expires=q.claim(time.time())
            with conn.cursor() as cur:
                cur.execute('UPDATE refresh_review SET lease_until=%s',(time.time()+.15,))
            conn.commit()
            def too_late(c):
                with IngestSession('municipio',municipio_slug='oviedo',conn=c):
                    with c.cursor() as cur:
                        cur.execute("INSERT INTO canonical_test VALUES('must rollback')")
                time.sleep(.2)
            from municipio.refresh_queue import StaleLease
            with patch('ingest.start_ingest_run',side_effect=start), patch('ingest.finish_ingest_run',side_effect=end):
                with self.assertRaises(StaleLease):
                    q.publish(expires,too_late)
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM canonical_test')
                self.assertEqual(cur.fetchone()[0],1)
                cur.execute('SELECT count(*) FROM ingest_test')
                self.assertEqual(cur.fetchone()[0],2)
            conn.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
            admin.commit()
            admin.close()
