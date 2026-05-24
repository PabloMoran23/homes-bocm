-- Texto normalizado del objeto del plan (visor HTML → resumenContenido).

ALTER TABLE homes.sigma_visor_expediente
  ADD COLUMN IF NOT EXISTS resumen_contenido TEXT;

UPDATE homes.sigma_visor_expediente
SET resumen_contenido = NULLIF(
  regexp_replace(btrim(visor_ficha->>'resumenContenido'), '\s+', ' ', 'g'),
  ''
)
WHERE resumen_contenido IS NULL
  AND visor_ficha->>'resumenContenido' IS NOT NULL
  AND btrim(visor_ficha->>'resumenContenido') <> '';

CREATE INDEX IF NOT EXISTS idx_homes_sigma_visor_resumen
  ON homes.sigma_visor_expediente (expediente_grupo)
  WHERE resumen_contenido IS NOT NULL;
