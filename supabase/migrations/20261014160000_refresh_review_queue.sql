SET search_path TO homes, public;

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

CREATE INDEX IF NOT EXISTS refresh_attempt_started_idx ON refresh_attempt(started);
ALTER TABLE refresh_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_metric ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON refresh_review, refresh_attempt, refresh_metric FROM anon, authenticated;
