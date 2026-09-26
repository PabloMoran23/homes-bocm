DROP FUNCTION IF EXISTS public.map_cm_portal_municipio(text, date, date);
DROP FUNCTION IF EXISTS homes.map_cm_portal_municipio(text, date, date);

-- 500 proyectos con actividad más reciente; al acercar el mapa, recorte por la zona visible.

CREATE OR REPLACE FUNCTION homes.map_cm_portal_municipio(
  p_slug text,
  p_from date,
  p_to date,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '25s'
AS $$
DECLARE
  lim_points integer := 500;
  lim_polys integer := 500;
  simplify_tol double precision := 0.0003;
  out jsonb;
BEGIN
  IF p_slug IS NULL OR btrim(p_slug) = ''
     OR (p_from IS NOT NULL AND p_to IS NOT NULL AND p_from > p_to) THEN
    RETURN jsonb_build_object(
      'points', jsonb_build_object('type', 'FeatureCollection', 'features', '[]'::jsonb),
      'polygons', jsonb_build_object('type', 'FeatureCollection', 'features', '[]'::jsonb),
      'meta', jsonb_build_object('proyectosEnRango', 0, 'proyectosSinFecha', 0, 'truncated', false)
    );
  END IF;

  WITH base AS MATERIALIZED (
    SELECT
      p.id,
      COALESCE(p.municipio, p.bocm_municipio, '') AS municipio,
      COALESCE(NULLIF(btrim(p.bocm_title), ''), NULLIF(btrim(p.denominacion), ''), p.id) AS titulo,
      to_char(homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob), 'YYYY-MM-DD') AS fecha,
      homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS bocm_pub_date,
      COALESCE(p.bocm_tipo_instrumento, '') AS tipo,
      COALESCE(p.enlace, p.visor_url, '') AS url,
      COALESCE(p.coord_source, '') AS coord_source,
      COALESCE(p.sector_key, '') AS sector_key,
      COALESCE(p.catalog_source, 'ayuntamiento-portal') AS catalog_source,
      p.has_geometry,
      p.geom_geojson,
      COALESCE(p.centroid_lng, p.lng) AS lng,
      COALESCE(p.centroid_lat, p.lat) AS lat,
      COALESCE(p.area_approx_m2, 0) AS area_m2
    FROM homes.proyecto p
    WHERE homes._proyecto_de_municipio(p_slug, p.municipio_slug, p.municipio, p.bocm_municipio)
      AND (
        (p_from IS NULL AND p_to IS NULL)
        OR (
          homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) IS NOT NULL
          AND (p_from IS NULL OR homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) >= p_from)
          AND (p_to IS NULL OR homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) <= p_to)
        )
      )
      AND (
        p_min_lng IS NULL OR p_max_lng IS NULL OR p_min_lat IS NULL OR p_max_lat IS NULL
        OR (
          COALESCE(p.bbox_max_lng, p.centroid_lng, p.lng) >= p_min_lng
          AND COALESCE(p.bbox_min_lng, p.centroid_lng, p.lng) <= p_max_lng
          AND COALESCE(p.bbox_max_lat, p.centroid_lat, p.lat) >= p_min_lat
          AND COALESCE(p.bbox_min_lat, p.centroid_lat, p.lat) <= p_max_lat
        )
      )
  ),
  props AS MATERIALIZED (
    SELECT
      b.*,
      jsonb_build_object(
        'id', b.id,
        'municipio', b.municipio,
        'titulo', b.titulo,
        'fecha', COALESCE(b.fecha, ''),
        'tipo', b.tipo,
        'url', b.url,
        'coordSource', b.coord_source,
        'sectorKey', b.sector_key,
        'catalogSource', b.catalog_source,
        'hasGeometry', b.has_geometry
      ) AS properties
    FROM base b
  ),
  point_ids AS (
    SELECT p.id
    FROM props p
    WHERE p.lat IS NOT NULL AND p.lng IS NOT NULL
      AND p.lng BETWEEN -180 AND 180
      AND p.lat BETWEEN -90 AND 90
      AND (
        p_min_lng IS NULL OR p_max_lng IS NULL OR p_min_lat IS NULL OR p_max_lat IS NULL
        OR (p.lng >= p_min_lng AND p.lng <= p_max_lng AND p.lat >= p_min_lat AND p.lat <= p_max_lat)
      )
      AND p.coord_source IS DISTINCT FROM 'municipio_centroid_jitter'
      AND NOT (
        p.has_geometry
        AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
      )
    ORDER BY p.bocm_pub_date DESC, p.id
    LIMIT lim_points
  ),
  points AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(p.lng, p.lat)),
      'properties', p.properties
    ) AS feature,
    p.bocm_pub_date,
    p.id
    FROM point_ids i
    JOIN props p ON p.id = i.id
  ),
  poly_ids AS (
    SELECT p.id
    FROM props p
    WHERE p.has_geometry
      AND p.geom_geojson IS NOT NULL
      AND jsonb_typeof(p.geom_geojson) = 'object'
      AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
      -- Madrid: por encima de 80 km² el polígono tapa la ciudad o la comunidad.
      AND (
        p_slug IS DISTINCT FROM 'madrid'
        OR COALESCE(p.area_m2, 0) <= 80000000
      )
    ORDER BY p.bocm_pub_date DESC NULLS LAST, p.area_m2 DESC, p.id
    LIMIT lim_polys
  ),
  polys AS MATERIALIZED (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', homes._proyecto_map_geometry(
        p.geom_geojson, p.lng, p.lat, true, simplify_tol
      ),
      'properties', p.properties
    ) AS feature,
    p.area_m2,
    p.id
    FROM poly_ids i
    JOIN props p ON p.id = i.id
  ),
  poly_ok AS MATERIALIZED (
    SELECT *
    FROM polys
    WHERE jsonb_typeof(feature->'geometry') = 'object'
      AND COALESCE(feature->'geometry'->>'type', '') IN ('Polygon', 'MultiPolygon')
  ),
  approx_pool AS (
    SELECT p.*
    FROM props p
    WHERE NOT EXISTS (SELECT 1 FROM point_ids i WHERE i.id = p.id)
      AND NOT EXISTS (SELECT 1 FROM poly_ok o WHERE o.id = p.id)
      AND (
        NOT (
          p.has_geometry
          AND p.geom_geojson IS NOT NULL
          AND jsonb_typeof(p.geom_geojson) = 'object'
          AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
        )
        OR (
          p_slug = 'madrid'
          AND COALESCE(p.area_m2, 0) > 80000000
        )
      )
  ),
  center AS (
    SELECT
      COALESCE(
        (SELECT avg(lng) FROM approx_pool WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90),
        (SELECT avg(COALESCE(centroid_lng, lng)) FROM homes.proyecto
          WHERE homes._proyecto_de_municipio(p_slug, municipio_slug, municipio, bocm_municipio)
            AND COALESCE(centroid_lng, lng) BETWEEN -180 AND 180
            AND COALESCE(centroid_lat, lat) BETWEEN -90 AND 90)
      ) AS lng,
      COALESCE(
        (SELECT avg(lat) FROM approx_pool WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90),
        (SELECT avg(COALESCE(centroid_lat, lat)) FROM homes.proyecto
          WHERE homes._proyecto_de_municipio(p_slug, municipio_slug, municipio, bocm_municipio)
            AND COALESCE(centroid_lng, lng) BETWEEN -180 AND 180
            AND COALESCE(centroid_lat, lat) BETWEEN -90 AND 90)
      ) AS lat
  ),
  approx_ids AS (
    SELECT p.id
    FROM approx_pool p
    ORDER BY
      CASE WHEN p_slug = 'madrid' AND COALESCE(p.area_m2, 0) > 80000000 THEN 0 ELSE 1 END,
      p.bocm_pub_date DESC NULLS LAST,
      p.id
    LIMIT 80
  ),
  approx AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', jsonb_build_object(
        'type', 'Point',
        'coordinates', jsonb_build_array(c.lng, c.lat)
      ),
      'properties', p.properties || jsonb_build_object(
        'approx', true,
        'fueraDeMapa', CASE
          WHEN p_slug = 'madrid' AND COALESCE(p.area_m2, 0) > 80000000 THEN 'extension'
          ELSE 'sin_coordenada'
        END
      )
    ) AS feature,
    p.bocm_pub_date,
    p.id
    FROM approx_ids i
    JOIN props p ON p.id = i.id
    CROSS JOIN center c
    WHERE c.lng IS NOT NULL AND c.lat IS NOT NULL
  ),
  sin_fecha AS (
    SELECT count(*)::int AS n
    FROM homes.proyecto p
    WHERE homes._proyecto_de_municipio(p_slug, p.municipio_slug, p.municipio, p.bocm_municipio)
      AND homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) IS NULL
  )
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'points', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY bocm_pub_date DESC, id) FROM points
      ), '[]'::jsonb)
    ),
    'polygons', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY area_m2 DESC, id) FROM poly_ok
      ), '[]'::jsonb)
    ),
    'approx', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY (feature->'properties'->>'fueraDeMapa') = 'extension' DESC, bocm_pub_date DESC NULLS LAST, id) FROM approx
      ), '[]'::jsonb)
    ),
    'meta', jsonb_build_object(
      'generatedAt', now()::text,
      'municipio', p_slug,
      'from', to_char(p_from, 'YYYY-MM-DD'),
      'to', to_char(p_to, 'YYYY-MM-DD'),
      'centerLng', (SELECT lng FROM center),
      'centerLat', (SELECT lat FROM center),
      'proyectosEnRango', (SELECT count(*)::int FROM base),
      'proyectosEnMapa',
        (SELECT count(*)::int FROM points)
        + (SELECT count(*)::int FROM poly_ok)
        + (SELECT count(*)::int FROM approx),
      'proyectosPoligonos', (SELECT count(*)::int FROM poly_ok),
      'proyectosPuntosReales', (SELECT count(*)::int FROM points),
      'proyectosAprox', (SELECT count(*)::int FROM approx),
      'proyectosAproxTotal', (SELECT count(*)::int FROM approx_pool),
      'proyectosSinFecha', (SELECT n FROM sin_fecha),
      'recorteEnVista', (p_min_lng IS NOT NULL AND p_max_lng IS NOT NULL AND p_min_lat IS NOT NULL AND p_max_lat IS NOT NULL),
      'limiteMapa', lim_polys,
      'truncated',
        (SELECT count(*) FROM point_ids) >= lim_points
        OR (SELECT count(*) FROM poly_ids) >= lim_polys
    )
  )
  INTO out;

  RETURN out;
END;
$$;

CREATE OR REPLACE FUNCTION public.map_cm_portal_municipio(
  p_slug text,
  p_from date,
  p_to date,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '30s'
AS $$ SELECT homes.map_cm_portal_municipio(p_slug, p_from, p_to, p_min_lng, p_min_lat, p_max_lng, p_max_lat); $$;

ALTER FUNCTION homes.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  SET statement_timeout = '30s';
ALTER FUNCTION public.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  SET statement_timeout = '30s';
GRANT EXECUTE ON FUNCTION homes.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  TO anon, authenticated, service_role;

