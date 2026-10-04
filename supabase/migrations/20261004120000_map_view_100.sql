-- A single budget for points and polygons. Rank scalar rows before reading geometry.
-- The initial camera uses density counts; subsequent requests only read the viewport.
CREATE OR REPLACE FUNCTION homes.map_cm_portal_view_100(
  p_slug text, p_from date, p_to date,
  p_min_lng double precision DEFAULT NULL, p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL, p_max_lat double precision DEFAULT NULL
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = homes, public SET statement_timeout = '25s'
AS $function$
WITH municipality AS (
  SELECT nombre, lng, lat FROM homes.municipio WHERE slug = p_slug
), municipality_rows AS MATERIALIZED (
  SELECT p.id, p.lat, p.lng, p.centroid_lat, p.centroid_lng, p.coord_source,
    p.area_approx_m2, p.bbox_min_lng, p.bbox_max_lng, p.bbox_min_lat, p.bbox_max_lat,
    p.has_geometry,
    homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date,
    EXISTS (SELECT 1 FROM homes.proyecto_investigacion inv WHERE inv.proyecto_id = p.id) AS researched
  FROM homes.proyecto p WHERE p.municipio_slug = p_slug
  UNION ALL
  SELECT p.id, p.lat, p.lng, p.centroid_lat, p.centroid_lng, p.coord_source,
    p.area_approx_m2, p.bbox_min_lng, p.bbox_max_lng, p.bbox_min_lat, p.bbox_max_lat,
    p.has_geometry,
    homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date,
    EXISTS (SELECT 1 FROM homes.proyecto_investigacion inv WHERE inv.proyecto_id = p.id) AS researched
  FROM homes.proyecto p
  WHERE NULLIF(btrim(COALESCE(p.municipio_slug, '')), '') IS NULL
    AND lower(btrim(COALESCE(p.municipio, p.bocm_municipio, ''))) = (SELECT lower(btrim(nombre)) FROM municipality)
), scoped AS MATERIALIZED (
  SELECT *, COALESCE(centroid_lng, lng) AS anchor_lng, COALESCE(centroid_lat, lat) AS anchor_lat
  FROM municipality_rows
  WHERE (p_from IS NULL OR act_date >= p_from) AND (p_to IS NULL OR act_date <= p_to)
), mapped AS MATERIALIZED (
  SELECT * FROM scoped
  WHERE anchor_lng BETWEEN -180 AND 180 AND anchor_lat BETWEEN -90 AND 90
    AND coord_source IS DISTINCT FROM 'municipio_centroid_jitter'
    AND (p_slug IS DISTINCT FROM 'madrid' OR NOT COALESCE(has_geometry, false)
      OR COALESCE(area_approx_m2, 0) <= 80000000 OR researched)
), extents AS (
  SELECT min(anchor_lng) AS west, max(anchor_lng) AS east,
    min(anchor_lat) AS south, max(anchor_lat) AS north FROM mapped
), seed AS (
  SELECT anchor_lng AS lng, anchor_lat AS lat FROM mapped
  ORDER BY
    pow(anchor_lng - COALESCE((SELECT lng FROM municipality), (SELECT (west + east) / 2 FROM extents)), 2)
    + pow(anchor_lat - COALESCE((SELECT lat FROM municipality), (SELECT (south + north) / 2 FROM extents)), 2),
    researched DESC, act_date DESC NULLS LAST, id
  LIMIT 1
), viewport AS (
  SELECT p_min_lng IS NOT NULL AND p_min_lat IS NOT NULL AND p_max_lng IS NOT NULL AND p_max_lat IS NOT NULL AS active,
    COALESCE(p_min_lng, west, (SELECT lng FROM municipality), -3.7) AS west,
    COALESCE(p_max_lng, east, (SELECT lng FROM municipality), -3.7) AS east,
    COALESCE(p_min_lat, south, (SELECT lat FROM municipality), 40.4) AS south,
    COALESCE(p_max_lat, north, (SELECT lat FROM municipality), 40.4) AS north
  FROM extents
), levels AS (
  SELECT step,
    CASE WHEN active OR (SELECT count(*) FROM mapped) <= 80 THEN (west + east) / 2 ELSE COALESCE((SELECT lng FROM seed), (west + east) / 2) END AS lng,
    CASE WHEN active OR (SELECT count(*) FROM mapped) <= 80 THEN (south + north) / 2 ELSE COALESCE((SELECT lat FROM seed), (south + north) / 2) END AS lat,
    GREATEST(east - west, 0.002) * pow(0.65, step) / 2 AS dx,
    GREATEST(north - south, 0.002) * pow(0.65, step) / 2 AS dy
  FROM viewport CROSS JOIN generate_series(0, 10) AS step
  WHERE step = 0 OR NOT active
), density AS MATERIALIZED (
  SELECT l.*, (SELECT count(*) FROM (
    SELECT 1 FROM mapped m
    WHERE m.anchor_lng BETWEEN l.lng - l.dx AND l.lng + l.dx
      AND m.anchor_lat BETWEEN l.lat - l.dy AND l.lat + l.dy
    LIMIT 101
  ) sample) AS n
  FROM levels l
), chosen AS (
  -- Prefer the widest frame with at most 80 projects (headroom for perspective).
  SELECT * FROM density ORDER BY
    CASE WHEN n BETWEEN 1 AND 80 THEN 0 WHEN n > 80 THEN 1 ELSE 2 END,
    CASE WHEN n BETWEEN 1 AND 80 THEN step ELSE -step END
  LIMIT 1
), ranked AS MATERIALIZED (
  SELECT m.* FROM mapped m CROSS JOIN chosen c
  WHERE m.anchor_lng BETWEEN c.lng - c.dx AND c.lng + c.dx
    AND m.anchor_lat BETWEEN c.lat - c.dy AND c.lat + c.dy
  ORDER BY researched DESC, act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id
  LIMIT 101
), selected AS (
  SELECT * FROM ranked ORDER BY researched DESC, act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id LIMIT 100
), features AS MATERIALIZED (
  SELECT jsonb_build_object('type', 'Feature',
    'geometry', CASE WHEN s.has_geometry AND jsonb_typeof(p.geom_geojson) = 'object'
        AND p.geom_geojson->>'type' IN ('Polygon', 'MultiPolygon')
      THEN homes._proyecto_map_geometry(p.geom_geojson, s.anchor_lng, s.anchor_lat, true, 0.0003)
      ELSE jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(s.anchor_lng, s.anchor_lat)) END,
    'properties', homes._proyecto_map_portal_row(p)) AS feature,
    s.researched, s.act_date, s.id
  FROM selected s JOIN homes.proyecto p ON p.id = s.id
), approx_ids AS (
  SELECT id FROM scoped WHERE NOT EXISTS (SELECT 1 FROM mapped m WHERE m.id = scoped.id)
    AND NOT (SELECT active FROM viewport) AND NOT EXISTS (SELECT 1 FROM selected)
  ORDER BY researched DESC, act_date DESC NULLS LAST, id LIMIT 16
), approx AS (
  SELECT jsonb_build_object('type', 'Feature',
    'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(
      COALESCE((SELECT lng FROM municipality), (SELECT lng FROM chosen)),
      COALESCE((SELECT lat FROM municipality), (SELECT lat FROM chosen)))),
    'properties', homes._proyecto_map_portal_row(p) || jsonb_build_object('approx', true, 'fueraDeMapa', 'sin_coordenada')) AS feature
  FROM approx_ids a JOIN homes.proyecto p ON p.id = a.id
)
SELECT jsonb_build_object(
  'generatedAt', now()::text,
  'points', jsonb_build_object('type', 'FeatureCollection', 'features', COALESCE((SELECT jsonb_agg(feature ORDER BY researched DESC, act_date DESC NULLS LAST, id) FROM features WHERE feature->'geometry'->>'type' = 'Point'), '[]'::jsonb)),
  'polygons', jsonb_build_object('type', 'FeatureCollection', 'features', COALESCE((SELECT jsonb_agg(feature ORDER BY researched, act_date DESC NULLS LAST, id) FROM features WHERE feature->'geometry'->>'type' IN ('Polygon', 'MultiPolygon')), '[]'::jsonb)),
  'approx', jsonb_build_object('type', 'FeatureCollection', 'features', COALESCE((SELECT jsonb_agg(feature) FROM approx), '[]'::jsonb)),
  'meta', jsonb_build_object(
    'municipio', p_slug, 'from', p_from, 'to', p_to,
    'proyectosEnRango', (SELECT count(*) FROM scoped),
    'proyectosEnMapa', (SELECT count(*) FROM features) + (SELECT count(*) FROM approx),
    'proyectosPoligonos', (SELECT count(*) FROM features WHERE feature->'geometry'->>'type' IN ('Polygon', 'MultiPolygon')),
    'proyectosPuntosReales', (SELECT count(*) FROM features WHERE feature->'geometry'->>'type' = 'Point'),
    'proyectosAprox', (SELECT count(*) FROM approx),
    'proyectosAproxTotal', (SELECT count(*) FROM scoped s WHERE NOT EXISTS (SELECT 1 FROM mapped m WHERE m.id = s.id)),
    'proyectosSinFecha', (SELECT count(*) FROM municipality_rows WHERE act_date IS NULL),
    'recorteEnVista', (SELECT active FROM viewport), 'limiteMapa', 100,
    'truncated', (SELECT count(*) FROM ranked) > 100,
    'autoFrame', CASE WHEN NOT (SELECT active FROM viewport) THEN
      (SELECT jsonb_build_object('west', lng - dx, 'east', lng + dx, 'south', lat - dy, 'north', lat + dy) FROM chosen) ELSE NULL END,
    'zoomStep', CASE WHEN (SELECT active FROM viewport) AND (SELECT count(*) FROM ranked) > 100 THEN 0.65 ELSE 0 END
  )
);
$function$;

CREATE OR REPLACE FUNCTION public.map_cm_portal_view_100(
  p_slug text, p_from date, p_to date,
  p_min_lng double precision DEFAULT NULL, p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL, p_max_lat double precision DEFAULT NULL
) RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = homes, public SET statement_timeout = '30s'
AS $$ SELECT homes.map_cm_portal_view_100(p_slug, p_from, p_to, p_min_lng, p_min_lat, p_max_lng, p_max_lat); $$;
REVOKE ALL ON FUNCTION homes.map_cm_portal_view_100(text, date, date, double precision, double precision, double precision, double precision) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.map_cm_portal_view_100(text, date, date, double precision, double precision, double precision, double precision) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION homes.map_cm_portal_view_100(text, date, date, double precision, double precision, double precision, double precision) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_portal_view_100(text, date, date, double precision, double precision, double precision, double precision) TO anon, authenticated, service_role;
NOTIFY pgrst, 'reload schema';
