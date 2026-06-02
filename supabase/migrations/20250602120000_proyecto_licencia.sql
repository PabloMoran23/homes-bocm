-- Paso 1 · Modelo de dominio: tablas funcionales proyecto + licencia.
-- Consolida columnas de project_boletin, sigma_*, link_* y actuacion_edificacion.
-- Las tablas legacy permanecen; el backfill es el paso 2.

CREATE TABLE homes.proyecto (
  id TEXT PRIMARY KEY,
  expediente_grupo TEXT UNIQUE,
  exp_numero_original TEXT,

  bocm_primary_id TEXT,
  bocm_sigma_match_type TEXT,
  bocm_sigma_match_score DOUBLE PRECISION,
  sigma_enlace_snapshot TEXT,

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
  sigma_synced_at TIMESTAMPTZ,
  raw_features_json JSONB,

  geom_geojson JSONB,
  bbox_min_lng DOUBLE PRECISION,
  bbox_min_lat DOUBLE PRECISION,
  bbox_max_lng DOUBLE PRECISION,
  bbox_max_lat DOUBLE PRECISION,
  centroid_lng DOUBLE PRECISION,
  centroid_lat DOUBLE PRECISION,
  area_approx_m2 DOUBLE PRECISION,
  geom_synced_at TIMESTAMPTZ,

  metric_fase TEXT,
  familia_expediente TEXT,
  genera_vivienda_nueva TEXT,
  metrics_json JSONB,
  hechos_json JSONB,
  fuentes_pdf_json JSONB,
  doc_role_principal TEXT,
  pdfs_procesados INTEGER NOT NULL DEFAULT 0,
  metrics_updated_at TIMESTAMPTZ,

  sin_datos_visor BOOLEAN NOT NULL DEFAULT false,
  visor_url TEXT,
  visor_cabecera JSONB,
  visor_ficha JSONB,
  resumen_contenido TEXT,
  tramitacion JSONB NOT NULL DEFAULT '[]'::jsonb,
  documentacion_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
  nti_listado_url TEXT,
  nti_documentos_total INTEGER,
  nti_documentos_muestra JSONB NOT NULL DEFAULT '[]'::jsonb,
  visor_fetched_at TIMESTAMPTZ,
  visor_raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,

  tipo_legal TEXT,
  escala TEXT,
  contenido_principal TEXT,
  fase_normalizada TEXT,
  categoria_proyecto TEXT,
  tipo_obra TEXT,
  clasificacion_confianza TEXT,
  clasificacion_fuentes JSONB NOT NULL DEFAULT '{}'::jsonb,

  bocm_source_id TEXT,
  bocm_pub_date DATE,
  bocm_art_num TEXT,
  bocm_title TEXT,
  bocm_pdf_path TEXT,
  bocm_pdf_url TEXT,
  bocm_txt_chars INTEGER,
  bocm_latency_s DOUBLE PRECISION,
  bocm_parse_error TEXT,
  bocm_es_relevante BOOLEAN,
  bocm_municipio TEXT,
  bocm_tipo_instrumento TEXT,
  bocm_nombre_sector TEXT,
  bocm_estado_tramitacion TEXT,
  bocm_fecha_acuerdo TEXT,
  bocm_organo TEXT,
  bocm_promotor TEXT,
  bocm_municipio_provincia TEXT,
  bocm_resumen TEXT,
  bocm_categorias_tematicas TEXT,
  bocm_economico_resumen TEXT,
  bocm_procedimiento_expediente TEXT,
  bocm_procedimiento_tipo TEXT,
  bocm_proyecto_fingerprint TEXT,
  bocm_chars_texto_total INTEGER,
  bocm_llm_max_context_chars INTEGER,
  bocm_texto_truncado_llm BOOLEAN,
  bocm_requiere_segunda_pasada BOOLEAN NOT NULL DEFAULT false,

  bocm_num_viviendas_max INTEGER,
  bocm_sup_total_m2 DOUBLE PRECISION,
  bocm_sup_edificable_m2 DOUBLE PRECISION,
  bocm_tipo_vivienda TEXT,
  bocm_fecha_fin_estimada TEXT,
  bocm_importe_total_eur DOUBLE PRECISION,
  metric_num_viviendas_max INTEGER,
  metric_sup_total_m2 DOUBLE PRECISION,
  metric_sup_edificable_m2 DOUBLE PRECISION,

  num_viviendas_max INTEGER,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  tipo_vivienda TEXT,
  fecha_fin_estimada TEXT,
  importe_total_eur DOUBLE PRECISION,

  municipio TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  coord_source TEXT,
  sector_key TEXT,
  sector_geo_key TEXT,

  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_homes_proyecto_expediente ON homes.proyecto (expediente_grupo) WHERE expediente_grupo IS NOT NULL;
CREATE INDEX idx_homes_proyecto_bocm_primary ON homes.proyecto (bocm_primary_id) WHERE bocm_primary_id IS NOT NULL;
CREATE INDEX idx_homes_proyecto_municipio ON homes.proyecto (municipio);
CREATE INDEX idx_homes_proyecto_coords ON homes.proyecto (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX idx_homes_proyecto_sigma_layer ON homes.proyecto (sigma_layer_kind);
CREATE INDEX idx_homes_proyecto_categoria ON homes.proyecto (categoria_proyecto) WHERE categoria_proyecto IS NOT NULL;
CREATE INDEX idx_homes_proyecto_bocm_pub_date ON homes.proyecto (bocm_pub_date) WHERE bocm_pub_date IS NOT NULL;

CREATE TABLE homes.licencia (
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

  proyecto_id TEXT REFERENCES homes.proyecto (id) ON DELETE SET NULL,
  proyecto_match_method TEXT,
  proyecto_match_score DOUBLE PRECISION,
  proyecto_sigma_layer_kind TEXT,
  proyecto_linked_at TIMESTAMPTZ,

  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_homes_licencia_inmueble ON homes.licencia (inmueble_id);
CREATE INDEX idx_homes_licencia_coords ON homes.licencia (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX idx_homes_licencia_proyecto ON homes.licencia (proyecto_id) WHERE proyecto_id IS NOT NULL;
CREATE INDEX idx_homes_licencia_tipo ON homes.licencia (tipo_expediente);
CREATE INDEX idx_homes_licencia_uso ON homes.licencia (uso);

ALTER TABLE homes.proyecto ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.licencia ENABLE ROW LEVEL SECURITY;

CREATE POLICY homes_proyecto_read ON homes.proyecto FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_licencia_read ON homes.licencia FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON homes.proyecto TO anon, authenticated;
GRANT SELECT ON homes.licencia TO anon, authenticated;
GRANT ALL ON homes.proyecto TO service_role;
GRANT ALL ON homes.licencia TO service_role;

COMMENT ON TABLE homes.proyecto IS
  'Actuación de planeamiento (dominio). Paso 1: esquema; backfill desde sigma_*, project_boletin.';
COMMENT ON TABLE homes.licencia IS
  'Actuación edificatoria (dominio). Paso 1: esquema; backfill desde actuacion_edificacion.';
