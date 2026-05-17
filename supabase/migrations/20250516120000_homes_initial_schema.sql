-- Homes / BOCM · esquema dedicado (no colisiona con tablas public.* de otras apps).

CREATE SCHEMA IF NOT EXISTS homes;

CREATE TABLE homes.schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO homes.schema_migrations (version) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE homes.source (
  id TEXT PRIMARY KEY,
  territorio_id TEXT NOT NULL,
  territorio_label TEXT NOT NULL
);

CREATE TABLE homes.project_boletin (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES homes.source (id),
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

CREATE INDEX idx_homes_project_source_date ON homes.project_boletin (source_id, pub_date);
CREATE INDEX idx_homes_project_municipio ON homes.project_boletin (municipio);
CREATE INDEX idx_homes_project_relevante ON homes.project_boletin (es_relevante);
CREATE INDEX idx_homes_project_coords ON homes.project_boletin (lat, lng) WHERE lat IS NOT NULL;

CREATE TABLE homes.sigma_catalog_expediente (
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

CREATE INDEX idx_homes_sigma_cat_layer ON homes.sigma_catalog_expediente (sigma_layer_kind);

CREATE TABLE homes.link_project_sigma (
  project_id TEXT NOT NULL REFERENCES homes.project_boletin (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_type TEXT,
  match_score DOUBLE PRECISION,
  sigma_enlace_snapshot TEXT,
  PRIMARY KEY (project_id)
);

CREATE INDEX idx_homes_link_sigma_exp ON homes.link_project_sigma (expediente_grupo);

CREATE TABLE homes.sigma_ambito_geom (
  expediente_grupo TEXT PRIMARY KEY REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
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

CREATE INDEX idx_homes_sigma_geom_bbox ON homes.sigma_ambito_geom (bbox_min_lng, bbox_max_lng, bbox_min_lat, bbox_max_lat);
CREATE INDEX idx_homes_sigma_geom_centroid ON homes.sigma_ambito_geom (centroid_lat, centroid_lng);

CREATE TABLE homes.inmueble (
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

CREATE INDEX idx_homes_inmueble_coords ON homes.inmueble (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX idx_homes_inmueble_ndp ON homes.inmueble (ndp_edificio);

CREATE TABLE homes.actuacion_edificacion (
  id BIGINT PRIMARY KEY,
  licencia_key TEXT NOT NULL UNIQUE,
  inmueble_id BIGINT REFERENCES homes.inmueble (id) ON DELETE SET NULL,
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

CREATE INDEX idx_homes_act_edif_inmueble ON homes.actuacion_edificacion (inmueble_id);
CREATE INDEX idx_homes_act_edif_coords ON homes.actuacion_edificacion (lat, lng) WHERE lat IS NOT NULL;

CREATE TABLE homes.link_licencia_sigma (
  licencia_id BIGINT NOT NULL REFERENCES homes.actuacion_edificacion (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_method TEXT NOT NULL,
  match_score DOUBLE PRECISION,
  sigma_layer_kind TEXT,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (licencia_id, expediente_grupo)
);

CREATE INDEX idx_homes_link_lic_sigma_exp ON homes.link_licencia_sigma (expediente_grupo);

CREATE TABLE homes.sigma_expediente_metric (
  expediente_grupo TEXT PRIMARY KEY REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  denominacion TEXT,
  fase_sigma TEXT,
  familia_expediente TEXT,
  genera_vivienda_nueva TEXT,
  num_viviendas_max INTEGER,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  metrics_json JSONB NOT NULL,
  hechos_json JSONB,
  fuentes_pdf_json JSONB,
  doc_role_principal TEXT,
  pdfs_procesados INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE homes.sigma_pdf_metric (
  id BIGSERIAL PRIMARY KEY,
  expediente_grupo TEXT NOT NULL REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  pdf_path TEXT NOT NULL UNIQUE,
  pdf_name TEXT,
  doc_type TEXT,
  doc_role TEXT,
  method TEXT,
  llm_model TEXT,
  processed_at TIMESTAMPTZ NOT NULL,
  num_viviendas_max INTEGER,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  tipo_vivienda TEXT,
  uso_principal TEXT,
  texto_util INTEGER,
  row_json JSONB NOT NULL,
  llm_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_homes_sigma_pdf_metric_exp ON homes.sigma_pdf_metric (expediente_grupo);

GRANT USAGE ON SCHEMA homes TO anon, authenticated, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA homes TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA homes TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA homes GRANT SELECT ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA homes GRANT ALL ON TABLES TO service_role;
