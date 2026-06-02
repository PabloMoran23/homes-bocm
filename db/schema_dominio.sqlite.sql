-- Modelo de dominio (paso 1) · SQLite local (sin schema homes).

CREATE TABLE IF NOT EXISTS proyecto (
  id TEXT PRIMARY KEY,
  expediente_grupo TEXT UNIQUE,
  exp_numero_original TEXT,

  bocm_primary_id TEXT,
  bocm_sigma_match_type TEXT,
  bocm_sigma_match_score REAL,
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
  object_id INTEGER,
  has_geometry INTEGER NOT NULL DEFAULT 0,
  sigma_synced_at TEXT,
  raw_features_json TEXT,

  geom_geojson TEXT,
  bbox_min_lng REAL,
  bbox_min_lat REAL,
  bbox_max_lng REAL,
  bbox_max_lat REAL,
  centroid_lng REAL,
  centroid_lat REAL,
  area_approx_m2 REAL,
  geom_synced_at TEXT,

  metric_fase TEXT,
  familia_expediente TEXT,
  genera_vivienda_nueva TEXT,
  metrics_json TEXT,
  hechos_json TEXT,
  fuentes_pdf_json TEXT,
  doc_role_principal TEXT,
  pdfs_procesados INTEGER NOT NULL DEFAULT 0,
  metrics_updated_at TEXT,

  sin_datos_visor INTEGER NOT NULL DEFAULT 0,
  visor_url TEXT,
  visor_cabecera TEXT,
  visor_ficha TEXT,
  resumen_contenido TEXT,
  tramitacion TEXT NOT NULL DEFAULT '[]',
  documentacion_urls TEXT NOT NULL DEFAULT '[]',
  nti_listado_url TEXT,
  nti_documentos_total INTEGER,
  nti_documentos_muestra TEXT NOT NULL DEFAULT '[]',
  visor_fetched_at TEXT,
  visor_raw_json TEXT NOT NULL DEFAULT '{}',

  tipo_legal TEXT,
  escala TEXT,
  contenido_principal TEXT,
  fase_normalizada TEXT,
  categoria_proyecto TEXT,
  tipo_obra TEXT,
  clasificacion_confianza TEXT,
  clasificacion_fuentes TEXT NOT NULL DEFAULT '{}',

  bocm_source_id TEXT,
  bocm_pub_date TEXT,
  bocm_art_num TEXT,
  bocm_title TEXT,
  bocm_pdf_path TEXT,
  bocm_pdf_url TEXT,
  bocm_txt_chars INTEGER,
  bocm_latency_s REAL,
  bocm_parse_error TEXT,
  bocm_es_relevante INTEGER,
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
  bocm_texto_truncado_llm INTEGER,
  bocm_requiere_segunda_pasada INTEGER NOT NULL DEFAULT 0,

  bocm_num_viviendas_max INTEGER,
  bocm_sup_total_m2 REAL,
  bocm_sup_edificable_m2 REAL,
  bocm_tipo_vivienda TEXT,
  bocm_fecha_fin_estimada TEXT,
  bocm_importe_total_eur REAL,
  metric_num_viviendas_max INTEGER,
  metric_sup_total_m2 REAL,
  metric_sup_edificable_m2 REAL,

  num_viviendas_max INTEGER,
  sup_total_m2 REAL,
  sup_edificable_m2 REAL,
  tipo_vivienda TEXT,
  fecha_fin_estimada TEXT,
  importe_total_eur REAL,

  municipio TEXT,
  lat REAL,
  lng REAL,
  coord_source TEXT,
  sector_key TEXT,
  sector_geo_key TEXT,
  programa_id TEXT,

  inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_proyecto_expediente ON proyecto (expediente_grupo);
CREATE INDEX IF NOT EXISTS idx_proyecto_bocm_primary ON proyecto (bocm_primary_id);
CREATE INDEX IF NOT EXISTS idx_proyecto_municipio ON proyecto (municipio);
CREATE INDEX IF NOT EXISTS idx_proyecto_coords ON proyecto (lat, lng);
CREATE INDEX IF NOT EXISTS idx_proyecto_sigma_layer ON proyecto (sigma_layer_kind);
CREATE INDEX IF NOT EXISTS idx_proyecto_categoria ON proyecto (categoria_proyecto);

CREATE TABLE IF NOT EXISTS licencia (
  id INTEGER PRIMARY KEY,
  licencia_key TEXT NOT NULL UNIQUE,

  inmueble_id INTEGER REFERENCES inmueble (id) ON DELETE SET NULL,

  anio_dataset INTEGER,
  fecha_alta TEXT,
  fecha_concesion TEXT,
  procedimiento TEXT,
  tipo_expediente TEXT,
  uso TEXT,
  interesado TEXT,
  objeto TEXT,
  unidad TEXT,
  lat REAL,
  lng REAL,
  raw_json TEXT,

  proyecto_id TEXT REFERENCES proyecto (id) ON DELETE SET NULL,
  proyecto_match_method TEXT,
  proyecto_match_score REAL,
  proyecto_sigma_layer_kind TEXT,
  proyecto_linked_at TEXT,

  inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_licencia_inmueble ON licencia (inmueble_id);
CREATE INDEX IF NOT EXISTS idx_licencia_coords ON licencia (lat, lng);
CREATE INDEX IF NOT EXISTS idx_licencia_proyecto ON licencia (proyecto_id);
CREATE INDEX IF NOT EXISTS idx_licencia_tipo ON licencia (tipo_expediente);
CREATE INDEX IF NOT EXISTS idx_licencia_uso ON licencia (uso);
