-- POC BOCM · esquema local SQLite 3 (compatible conceptualmente con PostgreSQL).
-- Migración futura pg: TIMESTAMP → TIMESTAMPTZ, BOOLEAN nativo, JSON → JSONB, INTEGER pk serial donde aplique.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS source (
  id TEXT PRIMARY KEY,
  territorio_id TEXT NOT NULL,
  territorio_label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_boletin (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source (id),
  pub_date TEXT NOT NULL,
  art_num TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  pdf_path TEXT,
  pdf_url TEXT,
  txt_chars INTEGER,
  latency_s REAL,
  parse_error TEXT,
  es_relevante INTEGER,
  municipio TEXT,
  tipo_instrumento TEXT,
  nombre_sector TEXT,
  estado_tramitacion TEXT,
  fecha_acuerdo TEXT,
  organo TEXT,
  num_viviendas_max INTEGER,
  fecha_fin_estimada TEXT,
  sup_total_m2 REAL,
  sup_edificable_m2 REAL,
  tipo_vivienda TEXT,
  promotor TEXT,
  municipio_provincia TEXT,
  resumen TEXT,
  categorias_tematicas TEXT,
  economico_resumen TEXT,
  procedimiento_expediente TEXT,
  procedimiento_tipo TEXT,
  importe_total_eur REAL,
  chars_texto_total INTEGER,
  llm_max_context_chars INTEGER,
  texto_truncado_llm INTEGER,
  requiere_segunda_pasada INTEGER NOT NULL DEFAULT 0,
  proyecto_fingerprint TEXT,
  sector_key TEXT,
  sector_geo_key TEXT,
  lat REAL,
  lng REAL,
  coord_source TEXT,
  inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (source_id, pub_date, art_num, proyecto_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_project_boletin_source_date ON project_boletin (source_id, pub_date);
CREATE INDEX IF NOT EXISTS idx_project_boletin_municipio ON project_boletin (municipio);
CREATE INDEX IF NOT EXISTS idx_project_boletin_relevante ON project_boletin (es_relevante);
CREATE INDEX IF NOT EXISTS idx_project_boletin_sector_key ON project_boletin (sector_key);

CREATE TABLE IF NOT EXISTS sigma_catalog_expediente (
  expediente_grupo TEXT PRIMARY KEY,
  exp_numero_original TEXT NOT NULL,
  sigma_layer_kind TEXT,
  denominacion TEXT,
  fase TEXT,
  fecha_aprob TEXT,
  infopublica_inicio TEXT,
  infopublica_fin TEXT,
  figura_codigo TEXT,
  tipo_figura TEXT,
  organo_tramitador TEXT,
  enlace TEXT,
  catalog_source TEXT,
  object_id INTEGER,
  has_geometry INTEGER NOT NULL DEFAULT 0,
  synced_at TEXT,
  raw_features_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sigma_cat_layer ON sigma_catalog_expediente (sigma_layer_kind);

CREATE TABLE IF NOT EXISTS link_project_sigma (
  project_id TEXT NOT NULL REFERENCES project_boletin (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_type TEXT,
  match_score REAL,
  sigma_enlace_snapshot TEXT,
  PRIMARY KEY (project_id)
);

CREATE INDEX IF NOT EXISTS idx_link_sigma_exp ON link_project_sigma (expediente_grupo);

CREATE TABLE IF NOT EXISTS sigma_vis_tramite (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  fecha TEXT,
  tramite TEXT,
  organo TEXT,
  visor_url TEXT,
  fetched_at TEXT,
  UNIQUE (expediente_grupo, orden)
);

CREATE INDEX IF NOT EXISTS idx_tramite_exp ON sigma_vis_tramite (expediente_grupo);

CREATE TABLE IF NOT EXISTS sigma_nti_document (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  url TEXT NOT NULL,
  titulo TEXT,
  tooltip TEXT,
  ruta_carpetas TEXT,
  tipodoc_nti TEXT,
  fecha_documento TEXT,
  fecha_creacion TEXT,
  fetched_at TEXT,
  local_path TEXT,
  sha256 TEXT,
  file_bytes INTEGER,
  content_type TEXT,
  http_status INTEGER,
  download_error TEXT,
  downloaded_at TEXT,
  UNIQUE (expediente_grupo, url)
);

CREATE INDEX IF NOT EXISTS idx_nti_exp ON sigma_nti_document (expediente_grupo);

CREATE TABLE IF NOT EXISTS sigma_boletin_sibling (
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  related_project_id TEXT NOT NULL REFERENCES project_boletin (id) ON DELETE CASCADE,
  bocm_date TEXT NOT NULL DEFAULT '',
  art_num TEXT NOT NULL DEFAULT '',
  title_short TEXT,
  es_relevante INTEGER,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (expediente_grupo, related_project_id)
);

CREATE INDEX IF NOT EXISTS idx_sibling_project ON sigma_boletin_sibling (related_project_id);
