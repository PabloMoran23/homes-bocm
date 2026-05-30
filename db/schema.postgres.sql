-- Variante PostgreSQL / Supabase (referencia para migración desde SQLite).

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source (
  id TEXT PRIMARY KEY,
  territorio_id TEXT NOT NULL,
  territorio_label TEXT NOT NULL
);

CREATE TABLE project_boletin (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source (id),
  pub_date DATE NOT NULL,
  art_num TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  pdf_path TEXT,
  pdf_url TEXT,
  txt_chars INTEGER,
  latency_s DOUBLE PRECISION,
  parse_error TEXT,
  es_relevante BOOLEAN,
  municipio TEXT,
  tipo_instrumento TEXT,
  nombre_sector TEXT,
  estado_tramitacion TEXT,
  fecha_acuerdo TEXT,
  organo TEXT,
  num_viviendas_max INTEGER,
  fecha_fin_estimada TEXT,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  tipo_vivienda TEXT,
  promotor TEXT,
  municipio_provincia TEXT,
  resumen TEXT,
  categorias_tematicas TEXT,
  economico_resumen TEXT,
  procedimiento_expediente TEXT,
  procedimiento_tipo TEXT,
  importe_total_eur DOUBLE PRECISION,
  chars_texto_total INTEGER,
  llm_max_context_chars INTEGER,
  texto_truncado_llm BOOLEAN,
  requiere_segunda_pasada BOOLEAN NOT NULL DEFAULT false,
  proyecto_fingerprint TEXT,
  sector_key TEXT,
  sector_geo_key TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  coord_source TEXT,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_id, pub_date, art_num, proyecto_fingerprint)
);

CREATE INDEX idx_project_boletin_source_date ON project_boletin (source_id, pub_date);
CREATE INDEX idx_project_boletin_municipio ON project_boletin (municipio);
CREATE INDEX idx_project_boletin_relevante ON project_boletin (es_relevante);
CREATE INDEX idx_project_boletin_sector_key ON project_boletin (sector_key);

CREATE TABLE sigma_catalog_expediente (
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
  object_id BIGINT,
  has_geometry BOOLEAN NOT NULL DEFAULT false,
  synced_at TIMESTAMPTZ,
  raw_features_json JSONB
);

CREATE INDEX idx_sigma_cat_layer ON sigma_catalog_expediente (sigma_layer_kind);

CREATE TABLE link_project_sigma (
  project_id TEXT NOT NULL REFERENCES project_boletin (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_type TEXT,
  match_score DOUBLE PRECISION,
  sigma_enlace_snapshot TEXT,
  PRIMARY KEY (project_id)
);

CREATE INDEX idx_link_sigma_exp ON link_project_sigma (expediente_grupo);

CREATE TABLE sigma_vis_tramite (
  id BIGSERIAL PRIMARY KEY,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  fecha TEXT,
  tramite TEXT,
  organo TEXT,
  visor_url TEXT,
  fetched_at TIMESTAMPTZ,
  UNIQUE (expediente_grupo, orden)
);

CREATE INDEX idx_tramite_exp ON sigma_vis_tramite (expediente_grupo);

CREATE TABLE sigma_nti_document (
  id BIGSERIAL PRIMARY KEY,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  url TEXT NOT NULL,
  titulo TEXT,
  tooltip TEXT,
  ruta_carpetas TEXT,
  tipodoc_nti TEXT,
  fecha_documento TEXT,
  fecha_creacion TEXT,
  fetched_at TIMESTAMPTZ,
  local_path TEXT,
  sha256 TEXT,
  file_bytes BIGINT,
  content_type TEXT,
  http_status INTEGER,
  download_error TEXT,
  downloaded_at TIMESTAMPTZ,
  UNIQUE (expediente_grupo, url)
);

CREATE INDEX idx_nti_exp ON sigma_nti_document (expediente_grupo);

CREATE TABLE sigma_boletin_sibling (
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  related_project_id TEXT NOT NULL REFERENCES project_boletin (id) ON DELETE CASCADE,
  bocm_date DATE,
  art_num TEXT,
  title_short TEXT,
  es_relevante BOOLEAN,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (expediente_grupo, related_project_id)
);

CREATE INDEX idx_sibling_project ON sigma_boletin_sibling (related_project_id);

-- v2: modelo por ubicación (ver schema_ubicacion.sql en SQLite).

CREATE TABLE sigma_ambito_geom (
  expediente_grupo TEXT PRIMARY KEY REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  geom_geojson JSONB NOT NULL,
  bbox_min_lng DOUBLE PRECISION NOT NULL,
  bbox_min_lat DOUBLE PRECISION NOT NULL,
  bbox_max_lng DOUBLE PRECISION NOT NULL,
  bbox_max_lat DOUBLE PRECISION NOT NULL,
  centroid_lng DOUBLE PRECISION,
  centroid_lat DOUBLE PRECISION,
  area_approx_m2 DOUBLE PRECISION,
  synced_at TIMESTAMPTZ
);

CREATE TABLE inmueble (
  id BIGSERIAL PRIMARY KEY,
  ndp_edificio TEXT NOT NULL UNIQUE,
  direccion TEXT,
  distrito TEXT,
  barrio TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  coord_source TEXT,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE actuacion_edificacion (
  id BIGSERIAL PRIMARY KEY,
  licencia_key TEXT NOT NULL UNIQUE,
  inmueble_id BIGINT REFERENCES inmueble (id) ON DELETE SET NULL,
  anio_dataset INTEGER,
  fecha_alta TEXT,
  fecha_concesion TEXT,
  procedimiento TEXT,
  tipo_expediente TEXT,
  uso TEXT,
  interesado TEXT,
  objeto TEXT,
  unidad TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  raw_json JSONB,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE link_licencia_sigma (
  licencia_id BIGINT NOT NULL REFERENCES actuacion_edificacion (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_method TEXT NOT NULL,
  match_score DOUBLE PRECISION,
  sigma_layer_kind TEXT,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (licencia_id, expediente_grupo)
);

CREATE TABLE hito (
  id BIGSERIAL PRIMARY KEY,
  entidad_tipo TEXT NOT NULL,
  entidad_id TEXT NOT NULL,
  fecha TEXT,
  tipo TEXT NOT NULL,
  organo TEXT,
  fuente TEXT,
  detalle_json JSONB,
  UNIQUE (entidad_tipo, entidad_id, fecha, tipo, organo)
);

-- Ver schema_sigma_programa.sql / migración 20250530140000_sigma_programa.sql
