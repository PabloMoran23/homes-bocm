-- Anuncios de tablón municipal (de momento, sedes Gestiona). Se guardan todos,
-- sin filtrar por tema; qué se muestra se decide después con `clase` y
-- `visible_radar`.
--
-- El tablón solo enseña lo que está en exposición: `first_seen_at` es cuándo lo
-- vimos por primera vez y `retirado_at` cuándo dejó de aparecer en una lectura
-- completa del tablón.

CREATE TABLE IF NOT EXISTS homes.anuncio (
  id TEXT PRIMARY KEY,                 -- 'gestiona-' || sha1(sede | documento)
  municipio_slug TEXT NOT NULL,
  fuente TEXT NOT NULL,                -- gestiona
  sede TEXT,                           -- host de la sede
  documento_id TEXT,                   -- uuid del documento en la sede
  url TEXT,
  titulo TEXT NOT NULL,
  descripcion TEXT,
  expediente TEXT,
  procedimiento TEXT,                  -- procedimiento del catálogo de la sede
  categoria TEXT,                      -- categoría del tablón
  fecha_publicacion DATE,
  fecha_fin DATE,
  clase TEXT NOT NULL DEFAULT 'otros', -- municipio/anuncio_clase.py
  subclase TEXT,
  clase_regla TEXT,                    -- catalogo | texto | manual
  clase_version INTEGER,
  visible_radar BOOLEAN,               -- NULL = sin decidir
  raw JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  retirado_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS anuncio_municipio_fecha
  ON homes.anuncio (municipio_slug, fecha_publicacion DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS anuncio_clase_fecha
  ON homes.anuncio (clase, fecha_publicacion DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS anuncio_first_seen
  ON homes.anuncio (first_seen_at DESC);
CREATE INDEX IF NOT EXISTS anuncio_vigentes
  ON homes.anuncio (municipio_slug) WHERE retirado_at IS NULL;

ALTER TABLE homes.anuncio ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    GRANT ALL ON homes.anuncio TO service_role;
  END IF;
END $$;
