-- Cover the foreign keys Supabase flags, and the municipio lookup the
-- investigación territorial job repeats. Non-destructive: indexes only.
--
-- The job's hot query is
--   SELECT DISTINCT ON (i.asunto_id) ...
--   FROM proyecto_investigacion_actual
--   JOIN proyecto_investigacion JOIN asunto
--   WHERE municipio = 'Madrid'
-- Without these indexes it seq-scans the investigation tables for 10–17s.

CREATE INDEX IF NOT EXISTS idx_homes_asunto_relacion_destino
  ON homes.asunto_relacion (destino_id);

CREATE INDEX IF NOT EXISTS idx_homes_asunto_relacion_investigacion
  ON homes.asunto_relacion (investigacion_id);

CREATE INDEX IF NOT EXISTS idx_homes_entrada_inv_archivo_asunto
  ON homes.entrada_investigacion_archivo_20261017 (asunto_id);

CREATE INDEX IF NOT EXISTS idx_homes_link_licencia_sigma_expediente
  ON homes.link_licencia_sigma (expediente_grupo);

CREATE INDEX IF NOT EXISTS idx_homes_proy_hallazgo_proyecto
  ON homes.proyecto_hallazgo (proyecto_id);

CREATE INDEX IF NOT EXISTS idx_homes_proy_inv_asunto
  ON homes.proyecto_investigacion (asunto_id)
  INCLUDE (proyecto_id, estado, investigado_at);

CREATE INDEX IF NOT EXISTS idx_homes_proy_inv_actual_investigacion
  ON homes.proyecto_investigacion_actual (investigacion_id);

CREATE INDEX IF NOT EXISTS idx_homes_proy_inv_lease_investigacion
  ON homes.proyecto_investigacion_lease (investigacion_id);

CREATE INDEX IF NOT EXISTS idx_homes_sigma_pdf_metric_expediente
  ON homes.sigma_pdf_metric (expediente_grupo);

CREATE INDEX IF NOT EXISTS idx_homes_asunto_municipio
  ON homes.asunto (lower(municipio), clave_identidad);

-- Slim, indexed replacement for the full-municipio scan. Direct DB role
-- (the research job) can call it. Not exposed to anon.
CREATE OR REPLACE FUNCTION homes.asuntos_investigados_municipio(
  p_municipio text,
  p_limit integer DEFAULT 200
)
RETURNS TABLE (
  asunto_id uuid,
  clave_identidad text,
  tipo text,
  titulo text,
  padre_id uuid,
  investigacion_id bigint,
  proyecto_id text,
  estado text
)
LANGUAGE sql
STABLE
SET search_path = homes, pg_catalog
AS $$
  SELECT DISTINCT ON (i.asunto_id)
    i.asunto_id,
    a.clave_identidad,
    a.tipo,
    a.titulo,
    a.padre_id,
    i.id,
    i.proyecto_id,
    i.estado
  FROM homes.asunto a
  JOIN homes.proyecto_investigacion i ON i.asunto_id = a.id
  JOIN homes.proyecto_investigacion_actual c ON c.investigacion_id = i.id
  WHERE p_municipio IS NOT NULL
    AND length(btrim(p_municipio)) > 0
    AND lower(a.municipio) = lower(btrim(p_municipio))
  ORDER BY i.asunto_id, i.investigado_at DESC NULLS LAST, i.id DESC
  LIMIT LEAST(GREATEST(COALESCE(p_limit, 200), 1), 500);
$$;

REVOKE ALL ON FUNCTION homes.asuntos_investigados_municipio(text, integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION homes.asuntos_investigados_municipio(text, integer) TO service_role;
