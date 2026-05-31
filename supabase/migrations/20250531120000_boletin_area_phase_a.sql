-- Fase A: boletín por zona — fecha en el JOIN, límites tempranos, stats acotados, sin full scan.

CREATE OR REPLACE FUNCTION homes.boletin_fecha_licencia(
  fecha_concesion text,
  fecha_alta text
) RETURNS date
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT COALESCE(
    CASE
      WHEN fecha_concesion ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(fecha_concesion FROM 1 FOR 10), 'DD/MM/YYYY')
      WHEN fecha_concesion ~ '^\d{4}-\d{2}-\d{2}' THEN fecha_concesion::date
      ELSE NULL
    END,
    CASE
      WHEN fecha_alta ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(fecha_alta FROM 1 FOR 10), 'DD/MM/YYYY')
      WHEN fecha_alta ~ '^\d{4}-\d{2}-\d{2}' THEN fecha_alta::date
      ELSE NULL
    END
  );
$$;

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
SET statement_timeout = '12s'
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
buildings_in_radius AS (
  SELECT
    ranked.id,
    ranked.ndp_edificio,
    ranked.direccion,
    ranked.distrito,
    ranked.lat,
    ranked.lng,
    ranked.distancia_m
  FROM (
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
    WHERE i.lat IS NOT NULL
      AND i.lng IS NOT NULL
      AND i.lat BETWEEN p.min_lat AND p.max_lat
      AND i.lng BETWEEN p.min_lng AND p.max_lng
      AND homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat) <= p.radius_m
    ORDER BY homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat)
    LIMIT 450
  ) ranked
),
center_pick AS (
  SELECT b.ndp_edificio, b.direccion, b.distrito, NULL::text AS barrio
  FROM buildings_in_radius b
  ORDER BY b.distancia_m
  LIMIT 1
),
lic_linked AS (
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
    COALESCE(homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta), DATE '1900-01-01') AS fecha_sort
  FROM homes.actuacion_edificacion ae
  INNER JOIN buildings_in_radius b ON b.id = ae.inmueble_id
  CROSS JOIN params p
  WHERE homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta) IS NULL
     OR homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta) >= p.cutoff
  ORDER BY COALESCE(homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta), DATE '1900-01-01') DESC
  LIMIT 151
),
lic_orphan AS (
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
    COALESCE(homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta), DATE '1900-01-01') AS fecha_sort
  FROM homes.actuacion_edificacion ae
  CROSS JOIN params p
  WHERE ae.inmueble_id IS NULL
    AND ae.lat IS NOT NULL
    AND ae.lng IS NOT NULL
    AND ae.lat BETWEEN p.min_lat AND p.max_lat
    AND ae.lng BETWEEN p.min_lng AND p.max_lng
    AND homes.haversine_m(p.center_lng, p.center_lat, ae.lng, ae.lat) <= p.radius_m
    AND (
      homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta) IS NULL
      OR homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta) >= p.cutoff
    )
  ORDER BY COALESCE(homes.boletin_fecha_licencia(ae.fecha_concesion, ae.fecha_alta), DATE '1900-01-01') DESC
  LIMIT 21
),
lic_pool AS (
  SELECT * FROM lic_linked
  UNION ALL
  SELECT * FROM lic_orphan
),
lic_stats AS (
  SELECT
    CASE
      WHEN (SELECT count(*)::int FROM lic_linked) >= 151 THEN 150
      ELSE (SELECT count(*)::int FROM lic_pool)
    END AS n,
    (SELECT count(*)::int FROM lic_linked) >= 151 AS capped
),
lic_map AS (
  SELECT * FROM lic_pool
  ORDER BY fecha_sort DESC
  LIMIT 25
),
sigma_ranked AS (
  SELECT
    'sigma' AS tipo,
    COALESCE(c.fecha_aprob, '01/01/' || split_part(c.exp_numero_original, '/', 2)) AS fecha,
    dist.distancia_m AS "distanciaM",
    LEFT(COALESCE(c.denominacion, g.expediente_grupo), 140) AS titulo,
    LEFT(CONCAT_WS(' · ', c.fase, 'A ' || dist.distancia_m::text || ' m'), 200) AS detalle,
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
  INNER JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
  CROSS JOIN params p
  CROSS JOIN LATERAL (
    SELECT round(homes.haversine_m(p.center_lng, p.center_lat, g.centroid_lng, g.centroid_lat))::int AS distancia_m
  ) dist
  WHERE g.centroid_lat IS NOT NULL
    AND g.centroid_lng IS NOT NULL
    AND g.bbox_max_lng >= p.min_lng
    AND g.bbox_min_lng <= p.max_lng
    AND g.bbox_max_lat >= p.min_lat
    AND g.bbox_min_lat <= p.max_lat
    AND dist.distancia_m <= p.radius_m
    AND COALESCE(
      CASE WHEN c.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN c.fecha_aprob::date ELSE NULL END,
      DATE '2000-01-01'
    ) >= p.cutoff
  ORDER BY COALESCE(
    CASE WHEN c.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN c.fecha_aprob::date ELSE NULL END,
    DATE '2000-01-01'
  ) DESC
  LIMIT 81
),
sigma_stats AS (
  SELECT
    LEAST(count(*)::int, 80) AS n,
    count(*) >= 81 AS capped
  FROM sigma_ranked
),
sigma_map AS (
  SELECT * FROM sigma_ranked
  ORDER BY fecha_sort DESC
  LIMIT 20
),
timeline_rows AS (
  SELECT * FROM (
    SELECT
      lp.tipo, lp.fecha, lp."distanciaM", lp.titulo, lp.detalle,
      lp.ndp, lp.direccion, lp.distrito,
      NULL::text AS "expedienteGrupo",
      NULL::boolean AS "contienePunto",
      NULL::text AS "sigmaLayerKind",
      lp.lat, lp.lng, lp.fecha_sort
    FROM lic_pool lp
    ORDER BY lp.fecha_sort DESC
    LIMIT 40
  ) lic_part
  UNION ALL
  SELECT * FROM (
    SELECT
      sr.tipo, sr.fecha, sr."distanciaM", sr.titulo, sr.detalle,
      NULL::text AS ndp, NULL::text AS direccion, NULL::text AS distrito,
      sr."expedienteGrupo", sr."contienePunto", sr."sigmaLayerKind",
      sr.lat, sr.lng, sr.fecha_sort
    FROM sigma_ranked sr
    ORDER BY sr.fecha_sort DESC
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
    'licencias', (SELECT n FROM lic_stats),
    'expedientesSigma', (SELECT n FROM sigma_stats),
    'eventos', (SELECT count(*)::int FROM timeline_ordered),
    'licenciasCapped', COALESCE((SELECT capped FROM lic_stats), false),
    'expedientesSigmaCapped', COALESCE((SELECT capped FROM sigma_stats), false)
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
LEFT JOIN center_pick c ON true;
$$;

ANALYZE homes.inmueble;
ANALYZE homes.actuacion_edificacion;
ANALYZE homes.sigma_ambito_geom;
