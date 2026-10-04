-- Include existing project summary and metrics in the bounded map payload for click cards.
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
), municipality_extents AS (
  SELECT min(COALESCE(centroid_lng, lng)) AS west, max(COALESCE(centroid_lng, lng)) AS east,
    min(COALESCE(centroid_lat, lat)) AS south, max(COALESCE(centroid_lat, lat)) AS north
  FROM municipality_rows
  WHERE COALESCE(centroid_lng, lng) BETWEEN -180 AND 180
    AND COALESCE(centroid_lat, lat) BETWEEN -90 AND 90
), center AS (
  SELECT COALESCE((SELECT lng FROM municipality), (west + east) / 2, -3.7) AS lng,
    COALESCE((SELECT lat FROM municipality), (south + north) / 2, 40.4) AS lat
  FROM municipality_extents
), viewport AS (
  SELECT p_min_lng IS NOT NULL AND p_min_lat IS NOT NULL AND p_max_lng IS NOT NULL AND p_max_lat IS NOT NULL AS active
), ranked AS MATERIALIZED (
  SELECT m.*,
    pow((m.anchor_lng - c.lng) * cos(radians(c.lat)), 2) + pow(m.anchor_lat - c.lat, 2) AS distance_to_center
  FROM mapped m CROSS JOIN center c CROSS JOIN viewport v
  WHERE NOT v.active OR (
    m.anchor_lng BETWEEN p_min_lng AND p_max_lng AND m.anchor_lat BETWEEN p_min_lat AND p_max_lat
  )
  ORDER BY
    CASE WHEN NOT v.active THEN pow((m.anchor_lng - c.lng) * cos(radians(c.lat)), 2) + pow(m.anchor_lat - c.lat, 2) ELSE 0 END,
    m.researched DESC, m.act_date DESC NULLS LAST, COALESCE(m.area_approx_m2, 0) DESC, m.id
  LIMIT 101
), selected AS MATERIALIZED (
  SELECT r.* FROM ranked r CROSS JOIN viewport v
  ORDER BY CASE WHEN NOT v.active THEN r.distance_to_center ELSE 0 END,
    researched DESC, act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id LIMIT 100
), initial_frame AS (
  SELECT CASE WHEN (SELECT count(*) FROM mapped) <= 100 THEN 'municipio' ELSE 'proyectos' END AS mode,
    CASE WHEN (SELECT count(*) FROM mapped) <= 100 THEN LEAST(COALESCE(e.west, c.lng - 0.02), c.lng)
      ELSE c.lng - GREATEST((SELECT max(abs(anchor_lng - c.lng)) FROM selected), 0.0005) END AS west,
    CASE WHEN (SELECT count(*) FROM mapped) <= 100 THEN GREATEST(COALESCE(e.east, c.lng + 0.02), c.lng)
      ELSE c.lng + GREATEST((SELECT max(abs(anchor_lng - c.lng)) FROM selected), 0.0005) END AS east,
    CASE WHEN (SELECT count(*) FROM mapped) <= 100 THEN LEAST(COALESCE(e.south, c.lat - 0.015), c.lat)
      ELSE c.lat - GREATEST((SELECT max(abs(anchor_lat - c.lat)) FROM selected), 0.0005) END AS south,
    CASE WHEN (SELECT count(*) FROM mapped) <= 100 THEN GREATEST(COALESCE(e.north, c.lat + 0.015), c.lat)
      ELSE c.lat + GREATEST((SELECT max(abs(anchor_lat - c.lat)) FROM selected), 0.0005) END AS north
  FROM center c CROSS JOIN municipality_extents e
), features AS MATERIALIZED (
  SELECT jsonb_build_object('type', 'Feature',
    'geometry', CASE WHEN s.has_geometry AND jsonb_typeof(p.geom_geojson) = 'object'
        AND p.geom_geojson->>'type' IN ('Polygon', 'MultiPolygon')
      THEN homes._proyecto_map_geometry(p.geom_geojson, s.anchor_lng, s.anchor_lat, true, 0.0003)
      ELSE jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(s.anchor_lng, s.anchor_lat)) END,
    'properties', homes._proyecto_map_portal_row(p) || jsonb_build_object('resumen', left(COALESCE(NULLIF(btrim(p.resumen_contenido), ''), NULLIF(btrim(p.bocm_resumen), '')), 600), 'fase', p.fase, 'numViviendas', p.num_viviendas_max, 'supM2', p.sup_total_m2, 'categoriaProyecto', p.categoria_proyecto, 'tipoObra', p.tipo_obra)) AS feature,
    s.researched, s.act_date, s.id
  FROM selected s JOIN homes.proyecto p ON p.id = s.id
), approx_ids AS (
  SELECT id FROM scoped WHERE NOT EXISTS (SELECT 1 FROM mapped m WHERE m.id = scoped.id)
    AND NOT (SELECT active FROM viewport) AND NOT EXISTS (SELECT 1 FROM selected)
  ORDER BY researched DESC, act_date DESC NULLS LAST, id LIMIT 16
), approx AS (
  SELECT jsonb_build_object('type', 'Feature',
    'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(
      COALESCE((SELECT lng FROM municipality), (SELECT lng FROM center)),
      COALESCE((SELECT lat FROM municipality), (SELECT lat FROM center)))),
    'properties', homes._proyecto_map_portal_row(p) || jsonb_build_object('resumen', left(COALESCE(NULLIF(btrim(p.resumen_contenido), ''), NULLIF(btrim(p.bocm_resumen), '')), 600), 'fase', p.fase, 'numViviendas', p.num_viviendas_max, 'supM2', p.sup_total_m2, 'categoriaProyecto', p.categoria_proyecto, 'tipoObra', p.tipo_obra) || jsonb_build_object('approx', true, 'fueraDeMapa', 'sin_coordenada')) AS feature
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
    'centerLng', (SELECT lng FROM center), 'centerLat', (SELECT lat FROM center),
    'initialFrameMode', (SELECT mode FROM initial_frame),
    'proyectosConUbicacion', (SELECT count(*) FROM mapped),
    'autoFrame', CASE WHEN NOT (SELECT active FROM viewport) THEN
      (SELECT jsonb_build_object('west', west, 'east', east, 'south', south, 'north', north) FROM initial_frame) ELSE NULL END
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
