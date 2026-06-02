-- Modelo de dominio (paso 1): tablas funcionales proyecto + licencia.
-- Referencia PostgreSQL / Supabase (schema homes).
-- Las tablas legacy (project_boletin, sigma_*, actuacion_edificacion) se mantienen hasta el backfill.

-- ---------------------------------------------------------------------------
-- proyecto — actuación de planeamiento / ordenación (fuentes: SIGMA, BOCM, visor, métricas)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proyecto (
  id TEXT PRIMARY KEY,
  expediente_grupo TEXT UNIQUE,
  exp_numero_original TEXT,

  -- Enlaces legacy (backfill paso 2)
  bocm_primary_id TEXT,
  bocm_sigma_match_type TEXT,
  bocm_sigma_match_score DOUBLE PRECISION,
  sigma_enlace_snapshot TEXT,

  -- Catálogo SIGMA (sigma_catalog_expediente)
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

  -- Ámbito geográfico (sigma_ambito_geom)
  geom_geojson JSONB,
  bbox_min_lng DOUBLE PRECISION,
  bbox_min_lat DOUBLE PRECISION,
  bbox_max_lng DOUBLE PRECISION,
  bbox_max_lat DOUBLE PRECISION,
  centroid_lng DOUBLE PRECISION,
  centroid_lat DOUBLE PRECISION,
  area_approx_m2 DOUBLE PRECISION,
  geom_synced_at TIMESTAMPTZ,

  -- Métricas expediente (sigma_expediente_metric)
  metric_fase TEXT,
  familia_expediente TEXT,
  genera_vivienda_nueva TEXT,
  metrics_json JSONB,
  hechos_json JSONB,
  fuentes_pdf_json JSONB,
  doc_role_principal TEXT,
  pdfs_procesados INTEGER NOT NULL DEFAULT 0,
  metrics_updated_at TIMESTAMPTZ,

  -- Visor municipal (sigma_visor_expediente)
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

  -- Clasificación heurística (sigma_visor_expediente)
  tipo_legal TEXT,
  escala TEXT,
  contenido_principal TEXT,
  fase_normalizada TEXT,
  categoria_proyecto TEXT,
  tipo_obra TEXT,
  clasificacion_confianza TEXT,
  clasificacion_fuentes JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Publicación BOCM principal (project_boletin — una por proyecto en backfill)
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

  -- Métricas por fuente (cuando difieren; consolidado en num_* / sup_*)
  bocm_num_viviendas_max INTEGER,
  bocm_sup_total_m2 DOUBLE PRECISION,
  bocm_sup_edificable_m2 DOUBLE PRECISION,
  bocm_tipo_vivienda TEXT,
  bocm_fecha_fin_estimada TEXT,
  bocm_importe_total_eur DOUBLE PRECISION,
  metric_num_viviendas_max INTEGER,
  metric_sup_total_m2 DOUBLE PRECISION,
  metric_sup_edificable_m2 DOUBLE PRECISION,

  -- Valores consolidados (mejor disponible)
  num_viviendas_max INTEGER,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  tipo_vivienda TEXT,
  fecha_fin_estimada TEXT,
  importe_total_eur DOUBLE PRECISION,

  -- Ubicación puntual
  municipio TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  coord_source TEXT,
  sector_key TEXT,
  sector_geo_key TEXT,

  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_proyecto_expediente ON proyecto (expediente_grupo) WHERE expediente_grupo IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proyecto_bocm_primary ON proyecto (bocm_primary_id) WHERE bocm_primary_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proyecto_municipio ON proyecto (municipio);
CREATE INDEX IF NOT EXISTS idx_proyecto_coords ON proyecto (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proyecto_sigma_layer ON proyecto (sigma_layer_kind);
CREATE INDEX IF NOT EXISTS idx_proyecto_categoria ON proyecto (categoria_proyecto) WHERE categoria_proyecto IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proyecto_bocm_pub_date ON proyecto (bocm_pub_date) WHERE bocm_pub_date IS NOT NULL;

-- ---------------------------------------------------------------------------
-- licencia — actuación edificatoria (open data + enlace a proyecto)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS licencia (
  id BIGINT PRIMARY KEY,
  licencia_key TEXT NOT NULL UNIQUE,

  -- Ubicación (tabla inmueble / ubicacion — separada)
  inmueble_id BIGINT,

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

  -- Enlace a proyecto de planeamiento (link_licencia_sigma)
  proyecto_id TEXT REFERENCES proyecto (id) ON DELETE SET NULL,
  proyecto_match_method TEXT,
  proyecto_match_score DOUBLE PRECISION,
  proyecto_sigma_layer_kind TEXT,
  proyecto_linked_at TIMESTAMPTZ,

  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_licencia_inmueble ON licencia (inmueble_id);
CREATE INDEX IF NOT EXISTS idx_licencia_coords ON licencia (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_licencia_proyecto ON licencia (proyecto_id) WHERE proyecto_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_licencia_tipo ON licencia (tipo_expediente);
CREATE INDEX IF NOT EXISTS idx_licencia_uso ON licencia (uso);
