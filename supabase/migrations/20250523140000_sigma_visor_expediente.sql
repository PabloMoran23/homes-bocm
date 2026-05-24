-- Persistencia del visor HTML municipal (VSURB) junto al catálogo SIGMA.

CREATE TABLE IF NOT EXISTS homes.sigma_visor_expediente (
  expediente_grupo TEXT PRIMARY KEY REFERENCES homes.sigma_catalog_expediente (expediente_grupo) ON DELETE CASCADE,
  sin_datos_visor BOOLEAN NOT NULL DEFAULT false,
  visor_url TEXT,
  visor_cabecera JSONB,
  visor_ficha JSONB,
  tramitacion JSONB NOT NULL DEFAULT '[]'::jsonb,
  documentacion_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
  nti_listado_url TEXT,
  nti_documentos_total INTEGER,
  nti_documentos_muestra JSONB NOT NULL DEFAULT '[]'::jsonb,
  fetched_at TIMESTAMPTZ,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_has_ficha
  ON homes.sigma_visor_expediente (expediente_grupo)
  WHERE visor_ficha IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_tramitacion
  ON homes.sigma_visor_expediente (expediente_grupo)
  WHERE jsonb_array_length(tramitacion) > 0;

ALTER TABLE homes.sigma_visor_expediente ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'homes'
      AND tablename = 'sigma_visor_expediente'
      AND policyname = 'homes_sigma_visor_read'
  ) THEN
    CREATE POLICY homes_sigma_visor_read
      ON homes.sigma_visor_expediente
      FOR SELECT
      TO anon, authenticated
      USING (true);
  END IF;
END $$;

GRANT SELECT ON homes.sigma_visor_expediente TO anon, authenticated;
GRANT ALL ON homes.sigma_visor_expediente TO service_role;
