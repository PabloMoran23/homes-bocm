-- Immutable source and derivative versions; current version lives in raw_features_json.
CREATE TABLE IF NOT EXISTS homes.proyecto_semantica_version (
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto(id) ON DELETE CASCADE,
  source_hash TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  template_version TEXT NOT NULL,
  source_record JSONB NOT NULL,
  derivation JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (proyecto_id, source_hash, contract_version, template_version)
);
