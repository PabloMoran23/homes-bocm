-- Map performance: indexed legacy municipality lookup and narrow ranking rows.
-- No changes to limits, date semantics, researched projects or geometry precision.
CREATE INDEX IF NOT EXISTS idx_homes_proyecto_map_legacy_municipio
  ON homes.proyecto (lower(btrim(COALESCE(municipio, bocm_municipio, ''))))
  WHERE NULLIF(btrim(COALESCE(municipio_slug, '')), '') IS NULL;

CREATE OR REPLACE FUNCTION homes.map_cm_portal_municipio(p_slug text, p_from date, p_to date, p_min_lng double precision DEFAULT NULL::double precision, p_min_lat double precision DEFAULT NULL::double precision, p_max_lng double precision DEFAULT NULL::double precision, p_max_lat double precision DEFAULT NULL::double precision)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'homes', 'public'
 SET statement_timeout TO '25s'
AS $function$
DECLARE
  lim_points integer := 500;
  lim_polys integer := 500;
  simplify_tol double precision := 0.0003;
  bbox_active boolean;
  municipio_nombre_normalizado text;
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

  SELECT lower(btrim(nombre)) INTO municipio_nombre_normalizado
  FROM homes.municipio WHERE slug = p_slug;

  IF bbox_active THEN
    -- Vista acercada: solo polígonos de la zona (sin lista «otros» ni recuentos globales).
    WITH in_bbox AS (
      SELECT
        p.id, p.area_approx_m2,
        homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date
      FROM homes.proyecto p
      WHERE p.municipio_slug = p_slug
        AND p.has_geometry
        AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
        AND (
          p_slug IS DISTINCT FROM 'madrid'
          OR COALESCE(p.area_approx_m2, 0) <= 80000000
          OR EXISTS (SELECT 1 FROM homes.proyecto_investigacion inv WHERE inv.proyecto_id = p.id)
        )
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
    destacados AS (
      SELECT *
      FROM in_bbox ib
      WHERE EXISTS (
        SELECT 1 FROM homes.proyecto_investigacion inv WHERE inv.proyecto_id = ib.id
      )
        AND (
          (p_from IS NULL AND p_to IS NULL)
          OR (
            ib.act_date IS NOT NULL
            AND (p_from IS NULL OR ib.act_date >= p_from)
            AND (p_to IS NULL OR ib.act_date <= p_to)
          )
        )
    ),
    poly_take AS (
      SELECT id FROM (SELECT id FROM poly_ranked ORDER BY act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id LIMIT lim_polys) ranked
      UNION
      SELECT id FROM destacados
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
          SELECT jsonb_agg(feature ORDER BY COALESCE((feature->'properties'->>'investigado')::boolean, false), area_m2 DESC, id)
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
  WITH municipio_rows AS MATERIALIZED (
    -- The legacy name fallback must not force a scan of every project.
    -- Keep NULL, empty and whitespace-only slugs equivalent to the old helper.
    SELECT p.id, p.lat, p.lng, p.area_approx_m2, p.coord_source,
      homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date,
      (p.has_geometry AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')) AS is_polygon
    FROM homes.proyecto p
    WHERE p.municipio_slug = p_slug
    UNION ALL
    SELECT p.id, p.lat, p.lng, p.area_approx_m2, p.coord_source,
      homes._proyecto_fecha_mapa(p.bocm_pub_date, p.fecha_aprob) AS act_date,
      (p.has_geometry AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')) AS is_polygon
    FROM homes.proyecto p
    WHERE NULLIF(btrim(COALESCE(p.municipio_slug, '')), '') IS NULL
      AND lower(btrim(COALESCE(p.municipio, p.bocm_municipio, ''))) = municipio_nombre_normalizado
  ),
  scoped AS (
    SELECT * FROM municipio_rows
    WHERE (p_from IS NULL AND p_to IS NULL)
      OR (act_date IS NOT NULL
        AND (p_from IS NULL OR act_date >= p_from)
        AND (p_to IS NULL OR act_date <= p_to))
  ),
  poly_ranked AS (
    SELECT s.*
    FROM scoped s
    WHERE s.is_polygon
      AND (p_slug IS DISTINCT FROM 'madrid' OR COALESCE(s.area_approx_m2, 0) <= 80000000)
    ORDER BY s.act_date DESC NULLS LAST, COALESCE(s.area_approx_m2, 0) DESC, s.id
    LIMIT lim_polys + 1
  ),
  destacados AS (
    SELECT s.*
    FROM scoped s
    WHERE EXISTS (
      SELECT 1 FROM homes.proyecto_investigacion inv WHERE inv.proyecto_id = s.id
    )
      AND s.is_polygon
  ),
  poly_take AS (
    SELECT id FROM (SELECT id FROM poly_ranked ORDER BY act_date DESC NULLS LAST, COALESCE(area_approx_m2, 0) DESC, id LIMIT lim_polys) ranked
    UNION
    SELECT id FROM destacados
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
  ),
  point_ranked AS (
    SELECT s.*
    FROM scoped s
    WHERE s.lat IS NOT NULL AND s.lng IS NOT NULL
      AND s.lng BETWEEN -180 AND 180
      AND s.lat BETWEEN -90 AND 90
      AND s.coord_source IS DISTINCT FROM 'municipio_centroid_jitter'
      AND NOT (
        s.is_polygon
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
          s.is_polygon
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
        SELECT jsonb_agg(feature ORDER BY COALESCE((feature->'properties'->>'investigado')::boolean, false), area_m2 DESC, id)
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
        SELECT count(*)::int FROM municipio_rows WHERE act_date IS NULL
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
$function$;
