"""Durable review queue. A successful DB write is not evidence of a source review."""
from __future__ import annotations

import hashlib
import math
import uuid
from contextlib import contextmanager

DAILY_ATTEMPTS = 72
HOST_DAILY_ATTEMPTS = 12
SOURCE_DAILY_ATTEMPTS = 3
LEASE_SECONDS = 15 * 60
REVIEW_SECONDS = 12 * 60
LEAD_SECONDS = 2 * 86400

DDL = """
CREATE TABLE IF NOT EXISTS refresh_review (
 slug TEXT PRIMARY KEY, host TEXT NOT NULL, config_hash TEXT NOT NULL,
 interval_seconds INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 last_complete DOUBLE PRECISION, due_at DOUBLE PRECISION NOT NULL, retry_at DOUBLE PRECISION NOT NULL,
 lease_token TEXT, lease_until DOUBLE PRECISION, failures INTEGER NOT NULL DEFAULT 0,
 last_error TEXT, last_write DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS refresh_metric (
 recorded DOUBLE PRECISION PRIMARY KEY, pending INTEGER NOT NULL, completed INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_attempt (
 token TEXT PRIMARY KEY, slug TEXT NOT NULL, host TEXT NOT NULL,
 started DOUBLE PRECISION NOT NULL, finished DOUBLE PRECISION, outcome TEXT, error TEXT,
 review_completed DOUBLE PRECISION, db_written DOUBLE PRECISION
);
"""


class Queue:
    def __init__(self, connection, *, sqlite=False):
        self.conn = connection
        self.sqlite = sqlite

    def execute(self, sql, args=()):
        cur = self.conn.cursor()
        cur.execute(sql if self.sqlite else sql.replace('?', '%s'), args)
        return cur

    @contextmanager
    def locked(self):
        if self.sqlite:
            self.execute('BEGIN IMMEDIATE')
        else:
            # Serializes claims, census and completion across CI runners.
            self.execute('SELECT pg_advisory_xact_lock(8562026)')
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def reconcile(self, sources, now):
        with self.locked():
            self.execute('UPDATE refresh_review SET enabled=0')
            for src in sources:
                self.execute('''INSERT INTO refresh_review
                    (slug,host,config_hash,interval_seconds,due_at,retry_at)
                    VALUES (?,?,?,?,?,?) ON CONFLICT (slug) DO UPDATE SET
                    host=excluded.host, interval_seconds=excluded.interval_seconds,
                    enabled=1, due_at=CASE WHEN refresh_review.config_hash != excluded.config_hash
                      THEN excluded.due_at ELSE refresh_review.due_at END,
                    retry_at=CASE WHEN refresh_review.config_hash != excluded.config_hash
                      THEN excluded.retry_at ELSE refresh_review.retry_at END,
                    last_complete=CASE WHEN refresh_review.config_hash != excluded.config_hash
                      THEN NULL ELSE refresh_review.last_complete END,
                    lease_token=CASE WHEN refresh_review.config_hash != excluded.config_hash
                      THEN NULL ELSE refresh_review.lease_token END,
                    lease_until=CASE WHEN refresh_review.config_hash != excluded.config_hash
                      THEN NULL ELSE refresh_review.lease_until END,
                    config_hash=excluded.config_hash''',
                    (src['slug'], src['host'], src['hash'], src['interval'], now, now))

    def claim(self, now, slugs=None):
        with self.locked():
            # Expired attempts remain visible; they also consume their daily budget.
            self.execute("UPDATE refresh_attempt SET finished=?, outcome='lease_expired' WHERE finished IS NULL AND started <= ?", (now, now-LEASE_SECONDS))
            counts = self.execute('SELECT slug,host FROM refresh_attempt WHERE started > ?', (now-86400,)).fetchall()
            if len(counts) >= DAILY_ATTEMPTS:
                return None
            rows = self.execute('''SELECT slug,host,due_at,failures FROM refresh_review
                WHERE enabled=1 AND due_at<=? AND retry_at<=?
                AND (lease_until IS NULL OR lease_until<=?) ORDER BY due_at,slug''', (now,now,now)).fetchall()
            for slug, host, due, failures in rows:
                if slugs and slug not in slugs:
                    continue
                if sum(s == slug for s,h in counts) >= SOURCE_DAILY_ATTEMPTS or sum(h == host for s,h in counts) >= HOST_DAILY_ATTEMPTS:
                    continue
                token = str(uuid.uuid4())
                self.execute('UPDATE refresh_review SET lease_token=?,lease_until=? WHERE slug=?', (token,now+LEASE_SECONDS,slug))
                self.execute('INSERT INTO refresh_attempt(token,slug,host,started) VALUES(?,?,?,?)', (token,slug,host,now))
                return {'slug':slug, 'token':token, 'failures':failures}
        return None

    def finish(self, job, now, *, complete=False, reviewed=False, written=False, error=None):
        with self.locked():
            row = self.execute('SELECT failures,interval_seconds FROM refresh_review WHERE slug=? AND lease_token=? AND lease_until>?', (job['slug'],job['token'],now)).fetchone()
            if row is None:
                return False  # Fencing: an old runner cannot complete a new lease.
            failures, interval = row
            if reviewed or complete:
                self.execute('UPDATE refresh_review SET last_complete=? WHERE slug=?', (now,job['slug']))
            if complete:
                self.execute('UPDATE refresh_review SET last_complete=?,due_at=?,retry_at=?,failures=0,last_error=NULL WHERE slug=?', (now,now+max(0,interval-LEAD_SECONDS),now,job['slug']))
            else:
                failures += 1
                jitter = int(hashlib.sha256(f"{job['slug']}:{failures}".encode()).hexdigest()[:4],16) % 300
                delay = min(86400, 900*2**min(failures-1,7)) + jitter
                self.execute('UPDATE refresh_review SET failures=?,retry_at=?,last_error=? WHERE slug=?', (failures,now+delay,error or 'incomplete_review',job['slug']))
            if written:
                self.execute('UPDATE refresh_review SET last_write=? WHERE slug=?', (now,job['slug']))
            self.execute('UPDATE refresh_review SET lease_token=NULL,lease_until=NULL WHERE slug=?', (job['slug'],))
            self.execute('UPDATE refresh_attempt SET finished=?,outcome=?,error=?,review_completed=?,db_written=? WHERE token=?', (now,'complete' if complete else 'failed',error,now if reviewed or complete else None,now if written else None,job['token']))
            return True

    def metrics(self, now):
        rows = self.execute('SELECT slug,last_complete,interval_seconds,due_at,last_error FROM refresh_review WHERE enabled=1').fetchall()
        ages = sorted(now-last if last is not None else now-due+interval for _,last,interval,due,_ in rows)
        violations = [slug for slug,last,interval,_,_ in rows if last is None or now-last>interval]
        attempts = self.execute('SELECT outcome,review_completed FROM refresh_attempt WHERE started>?', (now-86400,)).fetchall()
        previous = self.execute('SELECT pending FROM refresh_metric WHERE recorded<=? ORDER BY recorded DESC LIMIT 1',(now-86400,)).fetchone()
        pending = sum(due<=now for _,_,_,due,_ in rows)
        return {'backlog_change_24h':pending-previous[0] if previous else None,
                'backlog_growth_alarm':bool(previous and pending>previous[0]),
                'sources':len(rows),'daily_attempt_budget':DAILY_ATTEMPTS,
                'minimum_complete_per_day':math.ceil(sum(86400/r[2] for r in rows)),
                'complete_last_24h':sum(x[1] is not None for x in attempts),
                'attempts_last_24h':len(attempts),'pending':sum(due<=now for _,_,_,due,_ in rows),
                'max_age_days':max(ages,default=0)/86400,
                'p95_age_days':ages[max(0,math.ceil(.95*len(ages))-1)]/86400 if ages else 0,
                'sla_violations':violations, 'blocked':{s:e for s,_,_,_,e in rows if e},
                'capacity_alarm':sum(86400/r[2] for r in rows)>45}

    def checkpoint_metrics(self, now, metrics):
        with self.locked():
            self.execute('INSERT INTO refresh_metric(recorded,pending,completed) VALUES(?,?,?) ON CONFLICT(recorded) DO NOTHING', (now,metrics['pending'],metrics['complete_last_24h']))
            self.execute('DELETE FROM refresh_metric WHERE recorded<?',(now-90*86400,))
