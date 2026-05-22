-- Ficha ubicación: faltaba idx(inmueble_id) en remoto → 4× seq scan de 160k filas.
-- Reescritura: una pasada con CTEs; DISTINCT ON en lugar de jsonb_agg(DISTINCT …).

CREATE INDEX IF NOT EXISTS idx_homes_act_edif_inmueble
  ON homes.actuacion_edificacion (inmueble_id);

CREATE INDEX IF NOT EXISTS idx_homes_act_edif_inmueble_fechas
  ON homes.actuacion_edificacion (
    inmueble_id,
    fecha_concesion DESC NULLS LAST,
    fecha_alta DESC
  );

CREATE OR REPLACE FUNCTION homes.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  WITH inm AS (
    SELECT *
    FROM homes.inmueble
    WHERE ndp_edificio = trim(p_ndp)
  ),
  lic AS (
    SELECT
      ae.id,
      ae.licencia_key,
      ae.anio_dataset,
      ae.fecha_alta,
      ae.fecha_concesion,
      ae.procedimiento,
      ae.tipo_expediente,
      ae.uso,
      ae.interesado,
      ae.objeto,
      ae.unidad
    FROM homes.actuacion_edificacion ae
    INNER JOIN inm ON ae.inmueble_id = inm.id
    ORDER BY ae.fecha_concesion DESC NULLS LAST, ae.fecha_alta DESC
    LIMIT 200
  ),
  lic_total AS (
    SELECT COUNT(*)::int AS n
    FROM homes.actuacion_edificacion ae
    INNER JOIN inm ON ae.inmueble_id = inm.id
  ),
  sigma AS (
    SELECT DISTINCT ON (c.expediente_grupo)
      c.expediente_grupo,
      c.exp_numero_original,
      c.sigma_layer_kind,
      c.denominacion,
      c.fase,
      c.enlace,
      l.match_method,
      l.match_score
    FROM inm
    INNER JOIN homes.actuacion_edificacion ae ON ae.inmueble_id = inm.id
    INNER JOIN homes.link_licencia_sigma l ON l.licencia_id = ae.id
    INNER JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = l.expediente_grupo
    ORDER BY
      c.expediente_grupo,
      c.sigma_layer_kind,
      l.match_score DESC NULLS LAST
  )
  SELECT CASE
    WHEN NOT EXISTS (SELECT 1 FROM inm) THEN NULL
    ELSE jsonb_build_object(
      'inmueble',
      (SELECT to_jsonb(inm) FROM inm),
      'licencias',
      COALESCE(
        (
          SELECT jsonb_agg(to_jsonb(lic) ORDER BY lic.fecha_concesion DESC NULLS LAST, lic.fecha_alta DESC)
          FROM lic
        ),
        '[]'::jsonb
      ),
      'expedientesSigma',
      COALESCE(
        (
          SELECT jsonb_agg(to_jsonb(s) ORDER BY s.sigma_layer_kind, s.expediente_grupo)
          FROM sigma s
        ),
        '[]'::jsonb
      ),
      'tramitacionSigma',
      '{}'::jsonb,
      'stats',
      jsonb_build_object(
        'licenciasTotal',
        (SELECT n FROM lic_total),
        'expedientesSigma',
        (SELECT COUNT(*)::int FROM sigma)
      )
    )
  END;
$$;

CREATE OR REPLACE FUNCTION public.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.get_ubicacion_ficha(p_ndp);
$$;

ANALYZE homes.inmueble;
ANALYZE homes.actuacion_edificacion;
ANALYZE homes.link_licencia_sigma;
