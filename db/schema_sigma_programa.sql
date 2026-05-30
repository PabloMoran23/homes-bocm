-- Programas urbanísticos inferidos (varios expedientes SIGMA → un cluster).

CREATE TABLE IF NOT EXISTS sigma_programa (
  programa_id TEXT PRIMARY KEY,
  titulo TEXT NOT NULL,
  ambito_ordenacion TEXT,
  distrito TEXT,
  anio_inicio INTEGER,
  anio_fin INTEGER,
  confianza TEXT NOT NULL,
  metodo_agrupacion TEXT NOT NULL,
  miembros_count INTEGER NOT NULL,
  expediente_lider TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  generated_at TEXT NOT NULL DEFAULT (datetime('now')),
  version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_sigma_programa_ambito ON sigma_programa (ambito_ordenacion);
CREATE INDEX IF NOT EXISTS idx_sigma_programa_lider ON sigma_programa (expediente_lider);

CREATE TABLE IF NOT EXISTS sigma_programa_miembro (
  expediente_grupo TEXT PRIMARY KEY REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  programa_id TEXT NOT NULL REFERENCES sigma_programa (programa_id) ON DELETE CASCADE,
  rol TEXT NOT NULL,
  orden_fase INTEGER NOT NULL DEFAULT 0,
  confianza_rol TEXT,
  overlap_ratio REAL
);

CREATE INDEX IF NOT EXISTS idx_sigma_programa_miembro_prog ON sigma_programa_miembro (programa_id, orden_fase);
