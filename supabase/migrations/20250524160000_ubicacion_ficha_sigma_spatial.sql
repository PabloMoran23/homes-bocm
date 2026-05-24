-- Ficha ubicación: incluir TODOS los expedientes SIGMA cuyo ámbito contiene el edificio
-- (incl. PGOUM y normas de ciudad), no solo los enlazados vía licencias.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE OR REPLACE FUNCTION homes.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '15s'
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
  sigma_via_link AS (
    SELECT DISTINCT ON (c.expediente_grupo)
      c.expediente_grupo,
      c.exp_numero_original,
      c.sigma_layer_kind,
      c.denominacion,
      c.fase,
      c.enlace,
      l.match_method,
      l.match_score::double precision AS match_score
    FROM lic
    INNER JOIN homes.link_licencia_sigma l ON l.licencia_id = lic.id
    INNER JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = l.expediente_grupo
    ORDER BY
      c.expediente_grupo,
      l.match_score DESC NULLS LAST
  ),
  sigma_via_edificio AS (
    SELECT DISTINCT ON (c.expediente_grupo)
      c.expediente_grupo,
      c.exp_numero_original,
      c.sigma_layer_kind,
      c.denominacion,
      c.fase,
      c.enlace,
      'point_in_edificio'::text AS match_method,
      1.0::double precision AS match_score
    FROM inm
    INNER JOIN homes.sigma_ambito_geom g ON inm.lat IS NOT NULL AND inm.lng IS NOT NULL
    INNER JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
    WHERE g.bbox_min_lng <= inm.lng
      AND g.bbox_max_lng >= inm.lng
      AND g.bbox_min_lat <= inm.lat
      AND g.bbox_max_lat >= inm.lat
      AND public.ST_Contains(
        public.ST_SetSRID(public.ST_GeomFromGeoJSON(g.geom_geojson::text), 4326),
        public.ST_SetSRID(public.ST_MakePoint(inm.lng, inm.lat), 4326)
      )
    ORDER BY
      c.expediente_grupo,
      g.area_approx_m2 ASC NULLS LAST
  ),
  sigma AS (
    SELECT DISTINCT ON (expediente_grupo)
      expediente_grupo,
      exp_numero_original,
      sigma_layer_kind,
      denominacion,
      fase,
      enlace,
      match_method,
      match_score
    FROM (
      SELECT * FROM sigma_via_link
      UNION ALL
      SELECT * FROM sigma_via_edificio
    ) merged
    ORDER BY
      expediente_grupo,
      match_score DESC NULLS LAST,
      sigma_layer_kind
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
SET search_path = homes, public
SET statement_timeout = '15s'
AS $$
  SELECT homes.get_ubicacion_ficha(p_ndp);
$$;
