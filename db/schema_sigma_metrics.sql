-- Métricas extraídas de PDFs NTI (pipeline regex + LLM)

CREATE TABLE IF NOT EXISTS sigma_pdf_metric (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  expediente_grupo TEXT NOT NULL,
  pdf_path TEXT NOT NULL UNIQUE,
  pdf_name TEXT,
  doc_type TEXT,
  doc_role TEXT,
  method TEXT,
  llm_model TEXT,
  processed_at TEXT NOT NULL,
  num_viviendas_max INTEGER,
  sup_total_m2 REAL,
  sup_edificable_m2 REAL,
  tipo_vivienda TEXT,
  uso_principal TEXT,
  texto_util INTEGER,
  row_json TEXT NOT NULL,
  llm_error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sigma_pdf_metric_exp ON sigma_pdf_metric (expediente_grupo);
CREATE INDEX IF NOT EXISTS idx_sigma_pdf_metric_processed ON sigma_pdf_metric (processed_at);

CREATE TABLE IF NOT EXISTS sigma_expediente_metric (
  expediente_grupo TEXT PRIMARY KEY,
  denominacion TEXT,
  fase_sigma TEXT,
  familia_expediente TEXT,
  genera_vivienda_nueva TEXT,
  num_viviendas_max INTEGER,
  sup_total_m2 REAL,
  sup_edificable_m2 REAL,
  metrics_json TEXT NOT NULL,
  hechos_json TEXT,
  fuentes_pdf_json TEXT,
  doc_role_principal TEXT,
  pdfs_procesados INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sigma_pdf_extract_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
