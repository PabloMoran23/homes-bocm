"""Deterministic durable scheduling tests, without production credentials/network."""
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase

from municipio.refresh_queue import DDL, Queue, LEASE_SECONDS, DAILY_ATTEMPTS


class DurableQueueTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name)/'queue.db')
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(DDL)
        self.q = Queue(self.conn,sqlite=True)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def sources(self,n=1,host=None):
        return [dict(slug=f's{i:03}',host=host or f'host{i}',hash='v1',interval=15*86400) for i in range(n)]

    def test_restart_expired_lease_and_fencing(self):
        self.q.reconcile(self.sources(),1000)
        first = self.q.claim(1000)
        self.assertIsNone(self.q.claim(1001))
        self.conn.close()
        self.conn = sqlite3.connect(self.path)
        self.q = Queue(self.conn,sqlite=True)
        second = self.q.claim(1000+LEASE_SECONDS)
        self.assertNotEqual(first['token'],second['token'])
        self.assertFalse(self.q.finish(first,2000,complete=True))
        self.assertTrue(self.q.finish(second,2000,complete=True))
        self.assertFalse(self.q.finish(second,2001,complete=True))
        self.assertIsNone(self.q.claim(2002))
        self.assertEqual(self.q.metrics(2002)['complete_last_24h'],1)

    def test_failure_does_not_starve_other_source_or_move_review_timestamp(self):
        self.q.reconcile(self.sources(2),1000)
        first=self.q.claim(1000)
        self.q.finish(first,1001,error='blocked 429')
        second=self.q.claim(1001)
        self.assertNotEqual(first['slug'],second['slug'])
        self.q.finish(second,1002,complete=True)
        self.assertEqual(self.q.metrics(1003)['sla_violations'],[first['slug']])
        self.assertIn('blocked 429',self.q.metrics(1003)['blocked'].values())

    def test_changed_configuration_invalidates_due_without_losing_history(self):
        source=self.sources()
        self.q.reconcile(source,1000)
        self.q.finish(self.q.claim(1000),1001,complete=True)
        self.q.reconcile(source,1002)
        self.assertIsNone(self.q.claim(1002))
        source[0]['hash']='v2'
        self.q.reconcile(source,1003)
        self.assertIsNotNone(self.q.claim(1003))
        self.assertEqual(self.q.metrics(1003)['complete_last_24h'],1)

    def test_actual_72_daily_and_12_per_host_attempt_limits(self):
        self.q.reconcile(self.sources(100),1000)
        for i in range(DAILY_ATTEMPTS):
            job=self.q.claim(1000)
            self.assertIsNotNone(job)
            self.q.finish(job,1001,complete=True)
        self.assertIsNone(self.q.claim(1002))
        self.assertIsNotNone(self.q.claim(1000+86401))
        self.conn.execute('DELETE FROM refresh_attempt')
        self.conn.commit()
        self.q.reconcile(self.sources(100,host='shared'),1003)
        for i in range(12):
            job=self.q.claim(1003)
            self.assertIsNotNone(job)
            self.q.finish(job,1004,complete=True)
        self.assertIsNone(self.q.claim(1005))

    def test_674_sources_complete_every_15_days_with_retries_under_actual_limits(self):
        from municipio.refresh_dispatch import census
        sources=census()  # Real manifests, shared hosts and configured intervals.
        self.assertGreaterEqual(len(sources),674)
        self.q.reconcile(sources,0)
        completions={s['slug']:[] for s in sources}
        indexes={s['slug']:i for i,s in enumerate(sources)}
        attempts={}
        max_attempts=0
        # Two full cycles plus startup. 3/hour; each review lasts 12 minutes.
        # Every tenth source fails once per cycle; retries consume actual slots.
        for hour in range(24*45):
            for slot in range(3):
                now=hour*3600+slot*720
                job=self.q.claim(now)
                if not job:
                    continue
                key=(job['slug'],len(completions[job['slug']]))
                attempts[key]=attempts.get(key,0)+1
                complete=not (indexes[job['slug']]%10==0 and attempts[key]==1)
                self.q.finish(job,now+719,complete=complete,error=None if complete else 'transient')
                if complete:
                    completions[job['slug']].append(now+719)
                max_attempts=max(max_attempts,self.q.metrics(now+719)['attempts_last_24h'])
        print({'sources':len(sources),'max_attempts_24h':max_attempts,
               'first_cycle_max_days':round(max(v[0] for v in completions.values())/86400,3),
               'max_cycle_gap_days':round(max(b-a for v in completions.values() for a,b in zip(v,v[1:]))/86400,3),
               'complete_reviews':sum(map(len,completions.values())),
               'failed_attempts':sum(attempts.values())-sum(map(len,completions.values()))})
        self.assertLessEqual(max_attempts,72)
        for slug,stamps in completions.items():
            self.assertGreaterEqual(len(stamps),3,slug)
            self.assertLessEqual(stamps[0],15*86400,slug)
            self.assertTrue(all(b-a<=15*86400 for a,b in zip(stamps,stamps[1:])),slug)
            self.assertLessEqual(45*86400-stamps[-1],15*86400,slug)

    def test_oversubscribed_host_is_visible_sla_failure(self):
        self.q.reconcile(self.sources(674,host='one-host'),0)
        for day in range(15):
            for hour in range(24):
                for slot in range(3):
                    now=day*86400+hour*3600+slot*720
                    job=self.q.claim(now)
                    if job:
                        self.q.finish(job,now+719,complete=True)
        self.assertGreater(len(self.q.metrics(15*86400)['sla_violations']),400)
