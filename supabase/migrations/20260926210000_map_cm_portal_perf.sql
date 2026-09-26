-- Mapa municipio: menos trabajo por petición + índice para polígonos recientes.

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_municipio_map_poly
  ON homes.proyecto (municipio_slug, bocm_pub_date DESC NULLS LAST, id)
  WHERE has_geometry
    AND geom_geojson IS NOT NULL
    AND COALESCE(geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon');

DROP FUNCTION IF EXISTS public.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision);
DROP FUNCTION IF EXISTS homes.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision);

CREATE OR REPLACE FUNCTION homes._proyecto_map_portal_row(p homes.proyecto)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
  SELECT jsonb_build_object(
    'id', p.id,
    'municipio', COALESCE(p.municipio, p.bocm_municipio, ''),
    'titulo', COALESCE(NULLIF(btrim(p.bocm_title), ''), NULLIF(btrim(p.denominacion), ''), p.id),
    'fecha', COALESCE(to_char(homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob), 'YYYY-MM-DD'), ''),
    'tipo', COALESCE(p.bocm_tipo_instrumento, ''),
    'url', COALESCE(p.enlace, p.visor_url, ''),
    'coordSource', COALESCE(p.coord_source, ''),
    'sectorKey', COALESCE(p.sector_key, ''),
    'catalogSource', COALESCE(p.catalog_source, 'ayuntamiento-portal'),
    'hasGeometry', p.has_geometry
  );
$$;

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
  bbox_active boolean;
  out jsonb;
BEGIN
  IF p_slug IS NULL OR btrim(p_slug) = ''
     OR (p_from IS NOT NULL AND p_to IS NOT NULL AND p_from > p_to) THEN
    RETURN jsonb_build_object(
      'points', jsonb_build_object('type', 'FeatureCollection', 'features', '[]'::jsonb),
      'polygons', jsonb_build_object('type', 'FeatureCollection', 'features', '[]'::jsonb),
      'approx', jsonb_build_object('type', 'FeatureCollection', 'features', '[]'::jsonb),
      'meta', jsonb_build_object('proyectosEnRango', 0, 'proyectosSinFecha', 0, 'truncated', false)
    );
  END IF;

  bbox_active := p_min_lng IS NOT NULL AND p_max_lng IS NOT NULL
    AND p_min_lat IS NOT NULL AND p_max_lat IS NOT NULL;

  IF bbox_active THEN
    -- Vista acercada: solo polígonos de la zona (sin lista «otros» ni recuentos globales).
    WITH in_bbox AS (
      SELECT
        p.*,
        homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date
      FROM homes.proyecto p
      WHERE p.municipio_slug = p_slug
        AND p.has_geometry
        AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
        AND (p_slug IS DISTINCT FROM 'madrid' OR COALESCE(p.area_approx_m2, 0) <= 80000000)
        AND COALESCE(p.bbox_max_lng, p.centroid_lng, p.lng) >= p_min_lng
        AND COALESCE(p.bbox_min_lng, p.centroid_lng, p.lng) <= p_max_lng
        AND COALESCE(p.bbox_max_lat, p.centroid_lat, p.lat) >= p_min_lat
        AND COALESCE(p.bbox_min_lat, p.centroid_lat, p.lat) <= p_max_lat
    ),
    poly_ranked AS (
      SELECT *
      FROM in_bbox
      WHERE (p_from IS NULL AND p_to IS NULL)
        OR (
          act_date IS NOT NULL
          AND (p_from IS NULL OR act_date >= p_from)
          AND (p_to IS NULL OR act_date <= p_to)
        )
      ORDER BY act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id
      LIMIT lim_polys + 1
    ),
    poly_take AS (
      SELECT * FROM poly_ranked LIMIT lim_polys
    ),
    poly_ok AS (
      SELECT jsonb_build_object(
        'type', 'Feature',
        'geometry', homes._proyecto_map_geometry(
          p.geom_geojson,
          COALESCE(p.centroid_lng, p.lng),
          COALESCE(p.centroid_lat, p.lat),
          true,
          simplify_tol
        ),
        'properties', homes._proyecto_map_portal_row(p)
      ) AS feature,
      COALESCE(p.area_approx_m2, 0) AS area_m2,
      p.id
      FROM poly_take pt
      JOIN homes.proyecto p ON p.id = pt.id
    )
    SELECT jsonb_build_object(
      'generatedAt', now()::text,
      'points', jsonb_build_object('type', 'FeatureCollection', 'generatedAt', now()::text, 'features', '[]'::jsonb),
      'polygons', jsonb_build_object(
        'type', 'FeatureCollection',
        'generatedAt', now()::text,
        'features', COALESCE((
          SELECT jsonb_agg(feature ORDER BY area_m2 DESC, id)
          FROM poly_ok
          WHERE jsonb_typeof(feature->'geometry') = 'object'
            AND COALESCE(feature->'geometry'->>'type', '') IN ('Polygon', 'MultiPolygon')
        ), '[]'::jsonb)
      ),
      'approx', jsonb_build_object('type', 'FeatureCollection', 'generatedAt', now()::text, 'features', '[]'::jsonb),
      'meta', jsonb_build_object(
        'generatedAt', now()::text,
        'municipio', p_slug,
        'from', to_char(p_from, 'YYYY-MM-DD'),
        'to', to_char(p_to, 'YYYY-MM-DD'),
        'centerLng', NULL,
        'centerLat', NULL,
        'proyectosEnRango', (SELECT count(*)::int FROM poly_ranked),
        'proyectosEnMapa', (SELECT count(*)::int FROM poly_ok),
        'proyectosPoligonos', (SELECT count(*)::int FROM poly_ok),
        'proyectosPuntosReales', 0,
        'proyectosAprox', 0,
        'proyectosAproxTotal', 0,
        'proyectosSinFecha', NULL,
        'recorteEnVista', true,
        'limiteMapa', lim_polys,
        'truncated', (SELECT count(*) FROM poly_ranked) > lim_polys
      )
    )
    INTO out;
    RETURN out;
  END IF;

  -- Vista municipio completa: polígonos + puntos + «otros» (más caro, una sola vez al entrar).
  WITH scoped AS (
    SELECT
      p.*,
      homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date
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
  ),
  poly_ranked AS (
    SELECT s.*
    FROM scoped s
    WHERE s.has_geometry
      AND s.geom_geojson IS NOT NULL
      AND jsonb_typeof(s.geom_geojson) = 'object'
      AND COALESCE(s.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
      AND (p_slug IS DISTINCT FROM 'madrid' OR COALESCE(s.area_approx_m2, 0) <= 80000000)
    ORDER BY s.act_date DESC NULLS LAST, COALESCE(s.area_approx_m2, 0) DESC, s.id
    LIMIT lim_polys + 1
  ),
  poly_take AS (SELECT * FROM poly_ranked LIMIT lim_polys),
  poly_ok AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', homes._proyecto_map_geometry(
        p.geom_geojson,
        COALESCE(p.centroid_lng, p.lng),
        COALESCE(p.centroid_lat, p.lat),
        true,
        simplify_tol
      ),
      'properties', homes._proyecto_map_portal_row(p)
    ) AS feature,
    COALESCE(p.area_approx_m2, 0) AS area_m2,
    p.id
    FROM poly_take pt
    JOIN homes.proyecto p ON p.id = pt.id
  ),
  point_ranked AS (
    SELECT s.*
    FROM scoped s
    WHERE s.lat IS NOT NULL AND s.lng IS NOT NULL
      AND s.lng BETWEEN -180 AND 180
      AND s.lat BETWEEN -90 AND 90
      AND s.coord_source IS DISTINCT FROM 'municipio_centroid_jitter'
      AND NOT (
        s.has_geometry
        AND s.geom_geojson IS NOT NULL
        AND jsonb_typeof(s.geom_geojson) = 'object'
        AND COALESCE(s.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
      )
    ORDER BY s.act_date DESC NULLS LAST, s.id
    LIMIT lim_points
  ),
  points AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(p.lng, p.lat)),
      'properties', homes._proyecto_map_portal_row(p)
    ) AS feature,
    pr.act_date AS bocm_pub_date,
    p.id
    FROM point_ranked pr
    JOIN homes.proyecto p ON p.id = pr.id
  ),
  drawn AS (
    SELECT id FROM poly_take
    UNION
    SELECT id FROM point_ranked
  ),
  approx_pool AS (
    SELECT s.*
    FROM scoped s
    WHERE NOT EXISTS (SELECT 1 FROM drawn d WHERE d.id = s.id)
      AND (
        NOT (
          s.has_geometry
          AND s.geom_geojson IS NOT NULL
          AND jsonb_typeof(s.geom_geojson) = 'object'
          AND COALESCE(s.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
        )
        OR (p_slug = 'madrid' AND COALESCE(s.area_approx_m2, 0) > 80000000)
      )
  ),
  center AS (
    SELECT
      COALESCE(
        (SELECT avg(lng) FROM approx_pool WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90),
        (SELECT avg(COALESCE(centroid_lng, lng)) FROM homes.proyecto
          WHERE municipio_slug = p_slug
            AND COALESCE(centroid_lng, lng) BETWEEN -180 AND 180
            AND COALESCE(centroid_lat, lat) BETWEEN -90 AND 90)
      ) AS lng,
      COALESCE(
        (SELECT avg(lat) FROM approx_pool WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90),
        (SELECT avg(COALESCE(centroid_lat, lat)) FROM homes.proyecto
          WHERE municipio_slug = p_slug
            AND COALESCE(centroid_lng, lng) BETWEEN -180 AND 180
            AND COALESCE(centroid_lat, lat) BETWEEN -90 AND 90)
      ) AS lat
  ),
  approx_ids AS (
    SELECT p.id
    FROM approx_pool p
    ORDER BY
      CASE WHEN p_slug = 'madrid' AND COALESCE(p.area_approx_m2, 0) > 80000000 THEN 0 ELSE 1 END,
      p.act_date DESC NULLS LAST,
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
      'properties', homes._proyecto_map_portal_row(p) || jsonb_build_object(
        'approx', true,
        'fueraDeMapa', CASE
          WHEN p_slug = 'madrid' AND COALESCE(p.area_approx_m2, 0) > 80000000 THEN 'extension'
          ELSE 'sin_coordenada'
        END
      )
    ) AS feature,
    homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS bocm_pub_date,
    p.id
    FROM approx_ids i
    JOIN homes.proyecto p ON p.id = i.id
    CROSS JOIN center c
    WHERE c.lng IS NOT NULL AND c.lat IS NOT NULL
  )
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'points', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY bocm_pub_date DESC NULLS LAST, id) FROM points
      ), '[]'::jsonb)
    ),
    'polygons', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY area_m2 DESC, id)
        FROM poly_ok
        WHERE jsonb_typeof(feature->'geometry') = 'object'
          AND COALESCE(feature->'geometry'->>'type', '') IN ('Polygon', 'MultiPolygon')
      ), '[]'::jsonb)
    ),
    'approx', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((
        SELECT jsonb_agg(feature ORDER BY (feature->'properties'->>'fueraDeMapa') = 'extension' DESC, bocm_pub_date DESC NULLS LAST, id)
        FROM approx
      ), '[]'::jsonb)
    ),
    'meta', jsonb_build_object(
      'generatedAt', now()::text,
      'municipio', p_slug,
      'from', to_char(p_from, 'YYYY-MM-DD'),
      'to', to_char(p_to, 'YYYY-MM-DD'),
      'centerLng', (SELECT lng FROM center),
      'centerLat', (SELECT lat FROM center),
      'proyectosEnRango', (SELECT count(*)::int FROM scoped),
      'proyectosEnMapa',
        (SELECT count(*)::int FROM points)
        + (SELECT count(*)::int FROM poly_ok)
        + (SELECT count(*)::int FROM approx),
      'proyectosPoligonos', (SELECT count(*)::int FROM poly_ok),
      'proyectosPuntosReales', (SELECT count(*)::int FROM points),
      'proyectosAprox', (SELECT count(*)::int FROM approx),
      'proyectosAproxTotal', (SELECT count(*)::int FROM approx_pool),
      'proyectosSinFecha', (
        SELECT count(*)::int FROM homes.proyecto p
        WHERE homes._proyecto_de_municipio(p_slug, p.municipio_slug, p.municipio, p.bocm_municipio)
          AND homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) IS NULL
      ),
      'recorteEnVista', false,
      'limiteMapa', lim_polys,
      'truncated',
        (SELECT count(*) FROM poly_ranked) > lim_polys
        OR (SELECT count(*) FROM point_ranked) >= lim_points
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
SET statement_timeout = '25s'
AS $$ SELECT homes.map_cm_portal_municipio(p_slug, p_from, p_to, p_min_lng, p_min_lat, p_max_lng, p_max_lat); $$;

ALTER FUNCTION homes.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  SET statement_timeout = '25s';
ALTER FUNCTION public.map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)
  SET statement_timeout = '25s';
