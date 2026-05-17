-- POC BOCM · v2: modelo por ubicación (inmueble, edificación, ámbito SIGMA, enlaces).
-- Se aplica tras schema.sqlite.sql (migración versión 2).

-- Ámbito geográfico SIGMA (polígono + bbox para cruces espaciales).
CREATE TABLE IF NOT EXISTS sigma_ambito_geom (
  expediente_grupo TEXT PRIMARY KEY REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  geom_geojson TEXT NOT NULL,
  bbox_min_lng REAL NOT NULL,
  bbox_min_lat REAL NOT NULL,
  bbox_max_lng REAL NOT NULL,
  bbox_max_lat REAL NOT NULL,
  centroid_lng REAL,
  centroid_lat REAL,
  area_approx_m2 REAL,
  synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sigma_geom_bbox_lng ON sigma_ambito_geom (bbox_min_lng, bbox_max_lng);
CREATE INDEX IF NOT EXISTS idx_sigma_geom_bbox_lat ON sigma_ambito_geom (bbox_min_lat, bbox_max_lat);

-- Inmueble / edificio (ancla NDP Madrid).
CREATE TABLE IF NOT EXISTS inmueble (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ndp_edificio TEXT NOT NULL UNIQUE,
  direccion TEXT,
  distrito TEXT,
  barrio TEXT,
  lat REAL,
  lng REAL,
  coord_source TEXT,
  inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_inmueble_coords ON inmueble (lat, lng);

-- Actuación edificatoria = licencia urbanística (open data 300193).
CREATE TABLE IF NOT EXISTS actuacion_edificacion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_act_edif_inmueble ON actuacion_edificacion (inmueble_id);
CREATE INDEX IF NOT EXISTS idx_act_edif_coords ON actuacion_edificacion (lat, lng);
CREATE INDEX IF NOT EXISTS idx_act_edif_uso ON actuacion_edificacion (uso);
CREATE INDEX IF NOT EXISTS idx_act_edif_tipo ON actuacion_edificacion (tipo_expediente);

-- Enlace licencia ↔ expediente SIGMA por ubicación (punto en polígono).
CREATE TABLE IF NOT EXISTS link_licencia_sigma (
  licencia_id INTEGER NOT NULL REFERENCES actuacion_edificacion (id) ON DELETE CASCADE,
  expediente_grupo TEXT NOT NULL REFERENCES sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  match_method TEXT NOT NULL,
  match_score REAL,
  sigma_layer_kind TEXT,
  linked_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (licencia_id, expediente_grupo)
);

CREATE INDEX IF NOT EXISTS idx_link_lic_sigma_exp ON link_licencia_sigma (expediente_grupo);

-- Hitos fechados (tramitación SIGMA, fases, etc.).
CREATE TABLE IF NOT EXISTS hito (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entidad_tipo TEXT NOT NULL,
  entidad_id TEXT NOT NULL,
  fecha TEXT,
  tipo TEXT NOT NULL,
  organo TEXT,
  fuente TEXT,
  detalle_json TEXT,
  UNIQUE (entidad_tipo, entidad_id, fecha, tipo, organo)
);

CREATE INDEX IF NOT EXISTS idx_hito_entidad ON hito (entidad_tipo, entidad_id);

-- Vistas sobre catálogo SIGMA (ordenación vs suelo).
CREATE VIEW IF NOT EXISTS actuacion_ordenacion AS
SELECT
  expediente_grupo,
  exp_numero_original,
  sigma_layer_kind,
  denominacion,
  fase,
  fecha_aprob,
  infopublica_inicio,
  infopublica_fin,
  figura_codigo,
  enlace,
  catalog_source,
  has_geometry,
  synced_at
FROM sigma_catalog_expediente
WHERE sigma_layer_kind IN (
  'planeamiento',
  'tramitados_ad',
  'informacion_publica'
)
   OR catalog_source IN ('tramitados_ad', 'informacion_publica');

CREATE VIEW IF NOT EXISTS actuacion_suelo AS
SELECT
  expediente_grupo,
  exp_numero_original,
  sigma_layer_kind,
  denominacion,
  fase,
  fecha_aprob,
  figura_codigo,
  enlace,
  catalog_source,
  has_geometry,
  synced_at
FROM sigma_catalog_expediente
WHERE sigma_layer_kind IN ('gestion', 'urbanizacion', 'tramitados_gestion', 'tramitados_urbanizacion')
   OR catalog_source IN ('tramitados_gestion', 'tramitados_urbanizacion');
