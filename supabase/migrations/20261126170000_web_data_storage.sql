-- Web data files (web/public/data/*) move out of git into Supabase Storage.
--
-- Layout of the public bucket `web-data`:
--   objects/<sha256>.<ext>      content-addressed, immutable (cache 1 year)
--   manifests/<version>.json    one per release, immutable
--   manifest.json               pointer to the live release (cache 60 s)
--
-- The web never queries this table: browsers and server code read the
-- manifest and the objects from the Storage CDN. The table is the release
-- log for CI and for monitoring freshness.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'web-data',
  'web-data',
  true,
  104857600,
  ARRAY['application/json', 'application/geo+json']
)
ON CONFLICT (id) DO UPDATE
SET public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

CREATE TABLE IF NOT EXISTS homes.web_data_release (
  version text PRIMARY KEY,
  published_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL,
  git_sha text,
  run_id text,
  file_count integer NOT NULL,
  changed_files text[] NOT NULL DEFAULT '{}',
  total_bytes bigint NOT NULL,
  uploaded_bytes bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS web_data_release_published_at_idx
  ON homes.web_data_release (published_at DESC);

ALTER TABLE homes.web_data_release ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.web_data_release FROM PUBLIC, anon, authenticated;
GRANT SELECT ON homes.web_data_release TO service_role;
