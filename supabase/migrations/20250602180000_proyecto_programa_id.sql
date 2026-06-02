-- programa_id en proyecto + FKs de programas hacia dominio.

ALTER TABLE homes.proyecto
  ADD COLUMN IF NOT EXISTS programa_id TEXT;

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_programa
  ON homes.proyecto (programa_id)
  WHERE programa_id IS NOT NULL;

ALTER TABLE homes.sigma_programa
  DROP CONSTRAINT IF EXISTS sigma_programa_expediente_lider_fkey;

ALTER TABLE homes.sigma_programa
  ADD CONSTRAINT sigma_programa_expediente_lider_fkey
  FOREIGN KEY (expediente_lider)
  REFERENCES homes.proyecto (expediente_grupo)
  ON DELETE CASCADE;

ALTER TABLE homes.sigma_programa_miembro
  DROP CONSTRAINT IF EXISTS sigma_programa_miembro_expediente_grupo_fkey;

ALTER TABLE homes.sigma_programa_miembro
  ADD CONSTRAINT sigma_programa_miembro_expediente_grupo_fkey
  FOREIGN KEY (expediente_grupo)
  REFERENCES homes.proyecto (expediente_grupo)
  ON DELETE CASCADE;

ALTER TABLE homes.proyecto
  DROP CONSTRAINT IF EXISTS proyecto_programa_id_fkey;

ALTER TABLE homes.proyecto
  ADD CONSTRAINT proyecto_programa_id_fkey
  FOREIGN KEY (programa_id)
  REFERENCES homes.sigma_programa (programa_id)
  ON DELETE SET NULL;

COMMENT ON COLUMN homes.proyecto.programa_id IS
  'Cluster inferido de expedientes SIGMA co-territoriales (sigma_programa.programa_id).';
