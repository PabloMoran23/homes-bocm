-- Programas urbanísticos inferidos (cluster de expedientes SIGMA co-territoriales).

CREATE TABLE homes.sigma_programa (
  programa_id TEXT PRIMARY KEY,
  titulo TEXT NOT NULL,
  ambito_ordenacion TEXT,
  distrito TEXT,
  anio_inicio SMALLINT,
  anio_fin SMALLINT,
  confianza TEXT NOT NULL,
  metodo_agrupacion TEXT NOT NULL,
  miembros_count SMALLINT NOT NULL,
  expediente_lider TEXT NOT NULL REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_homes_sigma_programa_ambito ON homes.sigma_programa (ambito_ordenacion);
CREATE INDEX idx_homes_sigma_programa_lider ON homes.sigma_programa (expediente_lider);

CREATE TABLE homes.sigma_programa_miembro (
  expediente_grupo TEXT PRIMARY KEY REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  programa_id TEXT NOT NULL REFERENCES homes.sigma_programa (programa_id) ON DELETE CASCADE,
  rol TEXT NOT NULL,
  orden_fase SMALLINT NOT NULL DEFAULT 0,
  confianza_rol TEXT,
  overlap_ratio DOUBLE PRECISION
);

CREATE INDEX idx_homes_sigma_programa_miembro_prog ON homes.sigma_programa_miembro (programa_id, orden_fase);

GRANT SELECT ON homes.sigma_programa TO anon, authenticated, service_role;
GRANT SELECT ON homes.sigma_programa_miembro TO anon, authenticated, service_role;
