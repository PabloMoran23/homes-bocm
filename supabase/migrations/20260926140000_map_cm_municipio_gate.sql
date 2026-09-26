-- Entrada al mapa: lista ligera de municipios y GeoJSON de un solo municipio y fechas.
-- Sustituye la carga de todos los portales (homes.map_cm_portal) al abrir /explore.
-- Algunos portales guardan el polígono en UTM (ETRS89). El mapa solo entiende grados.

CREATE OR REPLACE FUNCTION homes._proyecto_map_geometry(
  p_geom jsonb,
  p_lng double precision,
  p_lat double precision,
  p_as_polygon boolean,
  p_simplify double precision
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  g public.geometry;
  simplified public.geometry;
  srid integer;
BEGIN
  IF p_as_polygon AND p_geom IS NOT NULL AND jsonb_typeof(p_geom) = 'object' THEN
    BEGIN
      g := public.ST_GeomFromGeoJSON(p_geom::text);
      IF g IS NOT NULL AND NOT public.ST_IsEmpty(g) THEN
        IF public.ST_XMax(g) > 180 OR public.ST_YMax(g) > 90 OR public.ST_XMin(g) < -180 OR public.ST_YMin(g) < -90 THEN
          -- Norte por debajo de ~3,8e6 m: Canarias (huso 28). El resto, península (huso 30).
          srid := CASE WHEN public.ST_YMax(g) < 3800000 THEN 25828 ELSE 25830 END;
          g := public.ST_Transform(public.ST_SetSRID(g, srid), 4326);
        ELSE
          g := public.ST_SetSRID(g, 4326);
        END IF;
        IF COALESCE(p_simplify, 0) > 0 AND public.ST_NPoints(g) > 24 THEN
          IF p_simplify >= 0.0005 THEN
            simplified := public.ST_Simplify(g, p_simplify);
          ELSE
            simplified := public.ST_SimplifyPreserveTopology(g, p_simplify);
          END IF;
          IF simplified IS NOT NULL AND NOT public.ST_IsEmpty(simplified) THEN
            RETURN public.ST_AsGeoJSON(simplified)::jsonb;
          END IF;
        END IF;
        RETURN public.ST_AsGeoJSON(g)::jsonb;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;

  IF p_lng IS NULL OR p_lat IS NULL OR p_lng < -180 OR p_lng > 180 OR p_lat < -90 OR p_lat > 90 THEN
    RETURN NULL;
  END IF;
  RETURN jsonb_build_object(
    'type', 'Point',
    'coordinates', jsonb_build_array(p_lng, p_lat)
  );
END;
$$;

CREATE OR REPLACE FUNCTION homes._proyecto_de_municipio(
  p_slug text,
  p_municipio_slug text,
  p_municipio text,
  p_bocm_municipio text
) RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(p_municipio_slug, '') = COALESCE(p_slug, '')
    OR (
      NULLIF(btrim(COALESCE(p_municipio_slug, '')), '') IS NULL
      AND lower(btrim(COALESCE(p_municipio, p_bocm_municipio, ''))) = (
        SELECT lower(btrim(nombre)) FROM homes.municipio WHERE slug = p_slug
      )
    );
$$;

CREATE OR REPLACE FUNCTION homes.map_cm_municipios()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '8s'
AS $$
  SELECT jsonb_build_object(
    'municipios', COALESCE((
      SELECT jsonb_agg(to_jsonb(s) ORDER BY s.nombre)
      FROM (
        SELECT
          slug,
          nombre,
          count(*)::int AS n,
          min(lng) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS west,
          min(lat) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS south,
          max(lng) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS east,
          max(lat) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS north
        FROM (
          SELECT m.slug, m.nombre, p.id,
            COALESCE(p.centroid_lng, p.lng) AS lng,
            COALESCE(p.centroid_lat, p.lat) AS lat
          FROM homes.municipio m
          JOIN homes.proyecto p ON p.municipio_slug = m.slug
          UNION ALL
          SELECT m.slug, m.nombre, p.id,
            COALESCE(p.centroid_lng, p.lng),
            COALESCE(p.centroid_lat, p.lat)
          FROM homes.municipio m
          JOIN homes.proyecto p
            ON p.municipio_slug IS NULL
           AND lower(btrim(COALESCE(p.municipio, p.bocm_municipio, ''))) = lower(btrim(m.nombre))
        ) u
        GROUP BY slug, nombre
      ) s
    ), '[]'::jsonb)
  );
$$;

CREATE OR REPLACE FUNCTION homes.map_cm_portal_municipio(
  p_slug text,
  p_from date,
  p_to date
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '8s'
AS $$
DECLARE
  lim_points integer := 800;
  lim_polys integer := 300;
  simplify_tol double precision := 0.0003;
  out jsonb;
BEGIN
  IF p_slug IS NULL OR btrim(p_slug) = '' OR p_from IS NULL OR p_to IS NULL OR p_from > p_to THEN
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
      to_char(p.bocm_pub_date, 'YYYY-MM-DD') AS fecha,
      p.bocm_pub_date,
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
      AND p.bocm_pub_date IS NOT NULL
      AND p.bocm_pub_date >= p_from
      AND p.bocm_pub_date <= p_to
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
    ORDER BY p.area_m2 DESC, p.id
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
    ORDER BY p.bocm_pub_date DESC, p.id
    LIMIT 80
  ),
  approx AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', jsonb_build_object(
        'type', 'Point',
        'coordinates', jsonb_build_array(c.lng, c.lat)
      ),
      'properties', p.properties || jsonb_build_object('approx', true)
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
      AND p.bocm_pub_date IS NULL
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
        SELECT jsonb_agg(feature ORDER BY bocm_pub_date DESC, id) FROM approx
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
      'truncated',
        (SELECT count(*) FROM point_ids) >= lim_points
        OR (SELECT count(*) FROM poly_ids) >= lim_polys
    )
  )
  INTO out;

  RETURN out;
END;
$$;

CREATE OR REPLACE FUNCTION public.map_cm_municipios()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '8s'
AS $$ SELECT homes.map_cm_municipios(); $$;

CREATE OR REPLACE FUNCTION public.map_cm_portal_municipio(
  p_slug text,
  p_from date,
  p_to date
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '8s'
AS $$ SELECT homes.map_cm_portal_municipio(p_slug, p_from, p_to); $$;

GRANT EXECUTE ON FUNCTION homes.map_cm_municipios() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.map_cm_portal_municipio(text, date, date) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_municipios() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_portal_municipio(text, date, date) TO anon, authenticated, service_role;
