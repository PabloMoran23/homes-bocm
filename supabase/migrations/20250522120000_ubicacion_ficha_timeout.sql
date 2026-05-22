-- Ficha ubicación: anon tiene statement_timeout=3s en PostgREST.
-- Sigma solo desde licencias ya limitadas (evita barrer todas las actuaciones).
-- La función eleva el timeout solo durante su ejecución (SECURITY DEFINER).

CREATE OR REPLACE FUNCTION homes.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '10s'
AS $$
  WITH inm AS (
    SELECT id, ndp_edificio, direccion, distrito, barrio, lat, lng, coord_source,
           inserted_at, updated_at
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
    WHERE ae.inmueble_id = (SELECT id FROM inm)
    ORDER BY ae.fecha_concesion DESC NULLS LAST, ae.fecha_alta DESC
    LIMIT 200
  ),
  lic_total AS (
    SELECT COUNT(*)::int AS n
    FROM homes.actuacion_edificacion ae
    WHERE ae.inmueble_id = (SELECT id FROM inm)
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
    FROM lic
    INNER JOIN homes.link_licencia_sigma l ON l.licencia_id = lic.id
    INNER JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = l.expediente_grupo
    ORDER BY
      c.expediente_grupo,
      c.sigma_layer_kind,
      l.match_score DESC NULLS LAST
  ),
  sigma_total AS (
    SELECT COUNT(DISTINCT l.expediente_grupo)::int AS n
    FROM homes.actuacion_edificacion ae
    INNER JOIN homes.link_licencia_sigma l ON l.licencia_id = ae.id
    WHERE ae.inmueble_id = (SELECT id FROM inm)
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
        (SELECT n FROM sigma_total)
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
SET statement_timeout = '10s'
AS $$
  SELECT homes.get_ubicacion_ficha(p_ndp);
$$;
