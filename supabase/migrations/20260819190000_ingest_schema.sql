-- Esquema mínimo de ingesta: municipio, publicacion, documento, ingest_run.
-- proyecto y licencia ya existen; se añaden columnas de origen (slug, fuente, id_origen).

CREATE TABLE IF NOT EXISTS homes.municipio (
  slug TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  provincia TEXT,
  comunidad_autonoma TEXT,
  ine TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  portal_url TEXT,
  adapter TEXT,
  last_ingest_at TIMESTAMPTZ,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_homes_municipio_ccaa
  ON homes.municipio (comunidad_autonoma);

INSERT INTO homes.municipio (slug, nombre, provincia, comunidad_autonoma)
VALUES ('madrid', 'Madrid', 'Madrid', 'comunidad-madrid')
ON CONFLICT (slug) DO NOTHING;

ALTER TABLE homes.proyecto
  ADD COLUMN IF NOT EXISTS municipio_slug TEXT REFERENCES homes.municipio (slug) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS fuente TEXT,
  ADD COLUMN IF NOT EXISTS id_origen TEXT;

ALTER TABLE homes.licencia
  ADD COLUMN IF NOT EXISTS municipio_slug TEXT REFERENCES homes.municipio (slug) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS fuente TEXT,
  ADD COLUMN IF NOT EXISTS id_origen TEXT;

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_municipio_slug
  ON homes.proyecto (municipio_slug);
CREATE INDEX IF NOT EXISTS idx_homes_proyecto_fuente
  ON homes.proyecto (fuente);
CREATE INDEX IF NOT EXISTS idx_homes_licencia_municipio_slug
  ON homes.licencia (municipio_slug);
CREATE INDEX IF NOT EXISTS idx_homes_licencia_id_origen
  ON homes.licencia (id_origen);

CREATE TABLE IF NOT EXISTS homes.publicacion (
  id TEXT PRIMARY KEY,
  boletin TEXT NOT NULL,
  fecha DATE,
  art_num TEXT,
  titulo TEXT NOT NULL DEFAULT '',
  pdf_url TEXT,
  pdf_path TEXT,
  municipio_slug TEXT REFERENCES homes.municipio (slug) ON DELETE SET NULL,
  municipio_nombre TEXT,
  resumen TEXT,
  num_viviendas_max INTEGER,
  fingerprint TEXT,
  proyecto_id TEXT REFERENCES homes.proyecto (id) ON DELETE SET NULL,
  es_relevante BOOLEAN,
  raw JSONB NOT NULL DEFAULT '{}'::jsonb,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_homes_publicacion_boletin_fecha
  ON homes.publicacion (boletin, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_homes_publicacion_municipio
  ON homes.publicacion (municipio_slug);
CREATE INDEX IF NOT EXISTS idx_homes_publicacion_proyecto
  ON homes.publicacion (proyecto_id);
CREATE INDEX IF NOT EXISTS idx_homes_publicacion_fingerprint
  ON homes.publicacion (fingerprint);

CREATE TABLE IF NOT EXISTS homes.documento (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  proyecto_id TEXT REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  publicacion_id TEXT REFERENCES homes.publicacion (id) ON DELETE SET NULL,
  url TEXT NOT NULL,
  titulo TEXT,
  fuente TEXT NOT NULL DEFAULT 'portal',
  extraido JSONB NOT NULL DEFAULT '{}'::jsonb,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (url)
);

CREATE INDEX IF NOT EXISTS idx_homes_documento_proyecto
  ON homes.documento (proyecto_id);
CREATE INDEX IF NOT EXISTS idx_homes_documento_publicacion
  ON homes.documento (publicacion_id);

CREATE TABLE IF NOT EXISTS homes.ingest_run (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scraper TEXT NOT NULL,
  municipio_slug TEXT REFERENCES homes.municipio (slug) ON DELETE SET NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running',
  rows_upserted JSONB NOT NULL DEFAULT '{}'::jsonb,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_homes_ingest_run_scraper
  ON homes.ingest_run (scraper, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_homes_ingest_run_municipio
  ON homes.ingest_run (municipio_slug);

ALTER TABLE homes.municipio ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.publicacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.documento ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.ingest_run ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS homes_municipio_read ON homes.municipio;
CREATE POLICY homes_municipio_read ON homes.municipio
  FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS homes_publicacion_read ON homes.publicacion;
CREATE POLICY homes_publicacion_read ON homes.publicacion
  FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS homes_documento_read ON homes.documento;
CREATE POLICY homes_documento_read ON homes.documento
  FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON homes.municipio, homes.publicacion, homes.documento
  TO anon, authenticated;
GRANT ALL ON homes.municipio, homes.publicacion, homes.documento, homes.ingest_run
  TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA homes TO service_role;

REVOKE ALL ON homes.ingest_run FROM anon, authenticated;

COMMENT ON TABLE homes.municipio IS
  'Catálogo de municipios. Los scrapers hacen upsert aquí antes de proyecto/licencia.';
COMMENT ON TABLE homes.publicacion IS
  'Artículo de boletín oficial (BOCM, CCAA, DOGC). Puede enlazar a un proyecto.';
COMMENT ON TABLE homes.documento IS
  'PDF o URL de expediente/publicación. extraido guarda métricas LLM.';
COMMENT ON TABLE homes.ingest_run IS
  'Log de cada ejecución de scraper. Sin lectura anónima.';
COMMENT ON COLUMN homes.proyecto.municipio_slug IS
  'FK a homes.municipio. Independiente de proyecto.municipio (nombre libre).';
COMMENT ON COLUMN homes.proyecto.fuente IS
  'Origen: ayuntamiento | sigma | boletin';
COMMENT ON COLUMN homes.proyecto.id_origen IS
  'Identificador en la fuente (expediente SIGMA, id del adapter, etc.).';
