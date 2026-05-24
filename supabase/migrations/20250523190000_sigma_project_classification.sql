-- Clasificación heurística SIGMA en 4 ejes: tipo legal, escala, contenido y fase.

ALTER TABLE homes.sigma_visor_expediente
  ADD COLUMN IF NOT EXISTS tipo_legal TEXT,
  ADD COLUMN IF NOT EXISTS escala TEXT,
  ADD COLUMN IF NOT EXISTS contenido_principal TEXT,
  ADD COLUMN IF NOT EXISTS fase_normalizada TEXT,
  ADD COLUMN IF NOT EXISTS categoria_proyecto TEXT,
  ADD COLUMN IF NOT EXISTS clasificacion_confianza TEXT,
  ADD COLUMN IF NOT EXISTS clasificacion_fuentes JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_categoria
  ON homes.sigma_visor_expediente (categoria_proyecto)
  WHERE categoria_proyecto IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_contenido
  ON homes.sigma_visor_expediente (contenido_principal)
  WHERE contenido_principal IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_escala
  ON homes.sigma_visor_expediente (escala)
  WHERE escala IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_fase_norm
  ON homes.sigma_visor_expediente (fase_normalizada)
  WHERE fase_normalizada IS NOT NULL;
