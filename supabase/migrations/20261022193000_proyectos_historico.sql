-- Diario append-only de proyectos. Renombra el histórico semántico y permite
-- una fila por cada cambio, también si el contenido vuelve a un estado anterior.

DO $$
BEGIN
  IF to_regclass('homes.proyecto_semantica_version') IS NOT NULL
     AND to_regclass('homes.proyectos_historico') IS NULL THEN
    ALTER TABLE homes.proyecto_semantica_version RENAME TO proyectos_historico;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS homes.proyectos_historico (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto(id) ON DELETE CASCADE,
  source_hash TEXT NOT NULL,
  contract_version TEXT NOT NULL,
  template_version TEXT NOT NULL,
  source_record JSONB NOT NULL,
  derivation JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE homes.proyectos_historico
  ADD COLUMN IF NOT EXISTS id BIGINT GENERATED ALWAYS AS IDENTITY;

DO $$
DECLARE
  pk name;
BEGIN
  SELECT conname INTO pk
  FROM pg_constraint
  WHERE conrelid = 'homes.proyectos_historico'::regclass
    AND contype = 'p';
  IF pk IS NULL THEN
    ALTER TABLE homes.proyectos_historico ADD PRIMARY KEY (id);
  ELSIF pk <> 'proyectos_historico_pkey' THEN
    EXECUTE format('ALTER TABLE homes.proyectos_historico DROP CONSTRAINT %I', pk);
    ALTER TABLE homes.proyectos_historico ADD PRIMARY KEY (id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS proyectos_historico_proyecto_created_idx
  ON homes.proyectos_historico (proyecto_id, created_at);

ALTER TABLE homes.proyectos_historico ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  seq regclass;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    GRANT ALL ON homes.proyectos_historico TO service_role;
    SELECT pg_get_serial_sequence('homes.proyectos_historico', 'id')::regclass INTO seq;
    IF seq IS NOT NULL THEN
      EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO service_role', seq);
    END IF;
  END IF;
END $$;
