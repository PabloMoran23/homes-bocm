-- Corrige sesgo espacial: filtrar por fecha y ordenar antes de limitar resultados.
-- Optimiza uniendo actuaciones a edificios en radio (índice) en lugar de haversine por fila.
CREATE OR REPLACE FUNCTION homes.boletin_area(
  p_lat double precision,
  p_lng double precision,
  p_radius_m double precision DEFAULT 600,
  p_months integer DEFAULT 24
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
WITH bounds AS (
  SELECT
    LEAST(GREATEST(COALESCE(p_radius_m, 600), 100), 3000) AS radius_m,
    LEAST(GREATEST(COALESCE(p_months, 24), 6), 120) AS months_i
),
params AS (
  SELECT
    b.radius_m,
    b.months_i,
    (CURRENT_DATE - (b.months_i * 30)) AS cutoff,
    p_lat AS center_lat,
    p_lng AS center_lng,
    p_lat - b.radius_m / 111000.0 AS min_lat,
    p_lat + b.radius_m / 111000.0 AS max_lat,
    p_lng - b.radius_m / (111000.0 * cos(radians(p_lat))) AS min_lng,
    p_lng + b.radius_m / (111000.0 * cos(radians(p_lat))) AS max_lng
  FROM bounds b
),
center_in_radius AS (
  SELECT i.ndp_edificio, i.direccion, i.distrito, i.barrio
  FROM homes.inmueble i
  CROSS JOIN params p
  WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
    AND homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat) <= p.radius_m
  ORDER BY homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat)
  LIMIT 1
),
center_fallback AS (
  SELECT i.ndp_edificio, i.direccion, i.distrito, i.barrio
  FROM homes.inmueble i
  CROSS JOIN params p
  WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
  ORDER BY homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat)
  LIMIT 1
),
center_pick AS (
  SELECT * FROM center_in_radius
  UNION ALL
  SELECT * FROM center_fallback
  WHERE NOT EXISTS (SELECT 1 FROM center_in_radius)
  LIMIT 1
),
buildings_in_radius AS (
  SELECT
    i.id,
    i.ndp_edificio,
    i.direccion,
    i.distrito,
    i.lat,
    i.lng,
    round(homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat))::int AS distancia_m
  FROM homes.inmueble i
  CROSS JOIN params p
  WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
    AND i.lat BETWEEN p.min_lat AND p.max_lat
    AND i.lng BETWEEN p.min_lng AND p.max_lng
    AND homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat) <= p.radius_m
),
lic_base AS (
  SELECT
    'licencia' AS tipo,
    COALESCE(ae.fecha_concesion, ae.fecha_alta) AS fecha,
    b.distancia_m AS "distanciaM",
    LEFT(COALESCE(ae.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
    LEFT(CONCAT_WS(' · ', ae.uso, ae.procedimiento, b.direccion), 200) AS detalle,
    b.ndp_edificio AS ndp,
    b.direccion,
    b.distrito,
    b.lat,
    b.lng,
    COALESCE(
      CASE WHEN ae.fecha_concesion ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_concesion from 1 for 10), 'DD/MM/YYYY')
           WHEN ae.fecha_concesion ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_concesion::date
           ELSE NULL END,
      CASE WHEN ae.fecha_alta ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_alta from 1 for 10), 'DD/MM/YYYY')
           WHEN ae.fecha_alta ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_alta::date
           ELSE DATE '1900-01-01' END
    ) AS fecha_sort
  FROM homes.actuacion_edificacion ae
  JOIN buildings_in_radius b ON b.id = ae.inmueble_id
  UNION ALL
  SELECT
    'licencia' AS tipo,
    COALESCE(ae.fecha_concesion, ae.fecha_alta) AS fecha,
    round(homes.haversine_m(p.center_lng, p.center_lat, ae.lng, ae.lat))::int AS "distanciaM",
    LEFT(COALESCE(ae.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
    LEFT(CONCAT_WS(' · ', ae.uso, ae.procedimiento, NULL), 200) AS detalle,
    NULL::text AS ndp,
    NULL::text AS direccion,
    NULL::text AS distrito,
    ae.lat,
    ae.lng,
    COALESCE(
      CASE WHEN ae.fecha_concesion ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_concesion from 1 for 10), 'DD/MM/YYYY')
           WHEN ae.fecha_concesion ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_concesion::date
           ELSE NULL END,
      CASE WHEN ae.fecha_alta ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_alta from 1 for 10), 'DD/MM/YYYY')
           WHEN ae.fecha_alta ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_alta::date
           ELSE DATE '1900-01-01' END
    ) AS fecha_sort
  FROM homes.actuacion_edificacion ae
  CROSS JOIN params p
  WHERE ae.inmueble_id IS NULL
    AND ae.lat IS NOT NULL AND ae.lng IS NOT NULL
    AND ae.lat BETWEEN p.min_lat AND p.max_lat
    AND ae.lng BETWEEN p.min_lng AND p.max_lng
    AND homes.haversine_m(p.center_lng, p.center_lat, ae.lng, ae.lat) <= p.radius_m
),
lic_filtered AS (
  SELECT lb.*
  FROM lic_base lb
  CROSS JOIN params p
  WHERE lb.fecha_sort IS NULL OR lb.fecha_sort >= p.cutoff
),
lic_map AS (
  SELECT * FROM lic_filtered
  ORDER BY fecha_sort DESC
  LIMIT 25
),
sigma_base AS (
  SELECT
    'sigma' AS tipo,
    COALESCE(c.fecha_aprob, '01/01/' || split_part(c.exp_numero_original, '/', 2)) AS fecha,
    round(homes.haversine_m(p.center_lng, p.center_lat, g.centroid_lng, g.centroid_lat))::int AS "distanciaM",
    LEFT(COALESCE(c.denominacion, g.expediente_grupo), 140) AS titulo,
    LEFT(CONCAT_WS(' · ', c.fase, 'A ' || round(homes.haversine_m(p.center_lng, p.center_lat, g.centroid_lng, g.centroid_lat))::text || ' m'), 200) AS detalle,
    g.expediente_grupo AS "expedienteGrupo",
    false AS "contienePunto",
    c.sigma_layer_kind AS "sigmaLayerKind",
    g.centroid_lat AS lat,
    g.centroid_lng AS lng,
    COALESCE(
      CASE WHEN c.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN c.fecha_aprob::date ELSE NULL END,
      DATE '2000-01-01'
    ) AS fecha_sort
  FROM homes.sigma_ambito_geom g
  JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
  CROSS JOIN params p
  WHERE g.centroid_lat IS NOT NULL AND g.centroid_lng IS NOT NULL
    AND g.bbox_max_lng >= p.min_lng AND g.bbox_min_lng <= p.max_lng
    AND g.bbox_max_lat >= p.min_lat AND g.bbox_min_lat <= p.max_lat
    AND homes.haversine_m(p.center_lng, p.center_lat, g.centroid_lng, g.centroid_lat) <= p.radius_m
    AND COALESCE(
      CASE WHEN c.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN c.fecha_aprob::date ELSE NULL END,
      DATE '2000-01-01'
    ) >= p.cutoff
),
sigma_map AS (
  SELECT * FROM sigma_base
  ORDER BY fecha_sort DESC
  LIMIT 20
),
timeline_rows AS (
  SELECT * FROM (
    SELECT
      lf.tipo, lf.fecha, lf."distanciaM", lf.titulo, lf.detalle,
      lf.ndp, lf.direccion, lf.distrito,
      NULL::text AS "expedienteGrupo",
      NULL::boolean AS "contienePunto",
      NULL::text AS "sigmaLayerKind",
      lf.lat, lf.lng, lf.fecha_sort
    FROM lic_filtered lf
    ORDER BY lf.fecha_sort DESC
    LIMIT 40
  ) lic_part
  UNION ALL
  SELECT * FROM (
    SELECT
      sb.tipo, sb.fecha, sb."distanciaM", sb.titulo, sb.detalle,
      NULL::text AS ndp, NULL::text AS direccion, NULL::text AS distrito,
      sb."expedienteGrupo", sb."contienePunto", sb."sigmaLayerKind",
      sb.lat, sb.lng, sb.fecha_sort
    FROM sigma_base sb
    ORDER BY sb.fecha_sort DESC
    LIMIT 40
  ) sigma_part
),
timeline_ordered AS (
  SELECT * FROM timeline_rows
  ORDER BY fecha_sort DESC
  LIMIT 80
)
SELECT jsonb_build_object(
  'center', jsonb_build_object(
    'lat', p.center_lat,
    'lng', p.center_lng,
    'ndp', c.ndp_edificio,
    'direccion', c.direccion,
    'distrito', c.distrito,
    'barrio', c.barrio
  ),
  'params', jsonb_build_object('radiusM', p.radius_m::int, 'months', p.months_i),
  'stats', jsonb_build_object(
    'licencias', (SELECT count(*)::int FROM lic_filtered),
    'expedientesSigma', (SELECT count(*)::int FROM sigma_base),
    'eventos', (SELECT count(*)::int FROM timeline_ordered)
  ),
  'licencias', COALESCE(
    (SELECT jsonb_agg(to_jsonb(lm) - 'fecha_sort' ORDER BY lm.fecha_sort DESC) FROM lic_map lm),
    '[]'::jsonb
  ),
  'expedientesSigma', COALESCE(
    (SELECT jsonb_agg(to_jsonb(sm) - 'fecha_sort' ORDER BY sm.fecha_sort DESC) FROM sigma_map sm),
    '[]'::jsonb
  ),
  'timeline', COALESCE(
    (SELECT jsonb_agg(to_jsonb(tr) - 'fecha_sort' ORDER BY tr.fecha_sort DESC) FROM timeline_ordered tr),
    '[]'::jsonb
  )
)
FROM params p
CROSS JOIN center_pick c;
$$;
