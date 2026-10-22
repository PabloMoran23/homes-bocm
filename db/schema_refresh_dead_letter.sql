-- Municipios que agotaron los reintentos de descarga. El cron no los vuelve a coger.

CREATE TABLE IF NOT EXISTS homes.municipio_dead_letter (
  slug TEXT PRIMARY KEY,
  failed_step TEXT,
  error TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE homes.municipio_dead_letter ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    GRANT ALL ON homes.municipio_dead_letter TO service_role;
  END IF;
END $$;
