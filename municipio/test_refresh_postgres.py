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
