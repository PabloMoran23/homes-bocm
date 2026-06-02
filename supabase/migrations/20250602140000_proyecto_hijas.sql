-- Tablas hijas de proyecto (dominio unificado).

CREATE TABLE homes.proyecto_bocm_publicacion (
  id BIGSERIAL PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  bocm_id TEXT NOT NULL UNIQUE,
  es_principal BOOLEAN NOT NULL DEFAULT false,
  bocm_source_id TEXT,
  pub_date DATE,
  art_num TEXT,
  title TEXT,
  es_relevante BOOLEAN,
  tipo_instrumento TEXT,
  nombre_sector TEXT,
  procedimiento_expediente TEXT,
  resumen TEXT,
  match_type TEXT,
  match_score DOUBLE PRECISION,
  inserted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_homes_proy_bocm_proyecto ON homes.proyecto_bocm_publicacion (proyecto_id);
CREATE INDEX idx_homes_proy_bocm_pub_date ON homes.proyecto_bocm_publicacion (pub_date);

CREATE TABLE homes.proyecto_tramite (
  id BIGSERIAL PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  fecha TEXT,
  tramite TEXT,
  organo TEXT,
  visor_url TEXT,
  fetched_at TIMESTAMPTZ,
  UNIQUE (proyecto_id, orden)
);

CREATE INDEX idx_homes_proy_tramite_proyecto ON homes.proyecto_tramite (proyecto_id);

CREATE TABLE homes.proyecto_documento (
  id BIGSERIAL PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  orden INTEGER NOT NULL,
  url TEXT NOT NULL,
  titulo TEXT,
  tooltip TEXT,
  ruta_carpetas TEXT,
  tipodoc_nti TEXT,
  fecha_documento TEXT,
  fuente TEXT NOT NULL DEFAULT 'nti',
  UNIQUE (proyecto_id, url)
);

CREATE INDEX idx_homes_proy_doc_proyecto ON homes.proyecto_documento (proyecto_id);

CREATE TABLE homes.proyecto_pdf_metric (
  id BIGSERIAL PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  pdf_path TEXT NOT NULL UNIQUE,
  pdf_name TEXT,
  doc_type TEXT,
  doc_role TEXT,
  method TEXT,
  llm_model TEXT,
  processed_at TIMESTAMPTZ,
  num_viviendas_max INTEGER,
  sup_total_m2 DOUBLE PRECISION,
  sup_edificable_m2 DOUBLE PRECISION,
  tipo_vivienda TEXT,
  uso_principal TEXT,
  row_json JSONB,
  llm_error TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_homes_proy_pdf_proyecto ON homes.proyecto_pdf_metric (proyecto_id);

ALTER TABLE homes.proyecto_bocm_publicacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.proyecto_tramite ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.proyecto_documento ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.proyecto_pdf_metric ENABLE ROW LEVEL SECURITY;

CREATE POLICY homes_proy_bocm_read ON homes.proyecto_bocm_publicacion FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_proy_tramite_read ON homes.proyecto_tramite FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_proy_doc_read ON homes.proyecto_documento FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_proy_pdf_read ON homes.proyecto_pdf_metric FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON homes.proyecto_bocm_publicacion TO anon, authenticated;
GRANT SELECT ON homes.proyecto_tramite TO anon, authenticated;
GRANT SELECT ON homes.proyecto_documento TO anon, authenticated;
GRANT SELECT ON homes.proyecto_pdf_metric TO anon, authenticated;
GRANT ALL ON homes.proyecto_bocm_publicacion TO service_role;
GRANT ALL ON homes.proyecto_tramite TO service_role;
GRANT ALL ON homes.proyecto_documento TO service_role;
GRANT ALL ON homes.proyecto_pdf_metric TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA homes TO service_role;
