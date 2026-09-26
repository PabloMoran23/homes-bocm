-- Mapa en vivo: solo el top-N por área del recorte visible.
-- 1) Elegir ids baratos (bbox + área).
-- 2) Simplificar geometría solo de esas filas.
-- Sin esto Postgres puede materializar ST_GeomFromGeoJSON de miles de polígonos.

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
BEGIN
  IF p_as_polygon AND p_geom IS NOT NULL AND jsonb_typeof(p_geom) = 'object' THEN
    BEGIN
      g := public.ST_SetSRID(public.ST_GeomFromGeoJSON(p_geom::text), 4326);
      IF g IS NOT NULL AND NOT public.ST_IsEmpty(g) THEN
        -- Polígonos ya simples: no gastar CPU en ST_Simplify.
        IF COALESCE(p_simplify, 0) > 0 AND public.ST_NPoints(g) > 24 THEN
          -- Vista amplia: ST_Simplify es más barato. Cerca: preserve topology.
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

  IF p_lng IS NULL OR p_lat IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN jsonb_build_object(
    'type', 'Point',
    'coordinates', jsonb_build_array(p_lng, p_lat)
  );
END;
$$;

CREATE OR REPLACE FUNCTION homes.map_sigma_geojson(
  p_zoom integer DEFAULT 11,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL,
  p_layer text DEFAULT 'ambitos',
  p_limit integer DEFAULT 80
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '12s'
AS $$
DECLARE
  zoom_i integer := LEAST(GREATEST(COALESCE(p_zoom, 11), 1), 22);
  lim integer;
  want_poly boolean := true;
  simplify_tol double precision;
  min_lng double precision;
  min_lat double precision;
  max_lng double precision;
  max_lat double precision;
  max_area double precision;
  features jsonb;
BEGIN

  -- Sin bbox: ciudad de Madrid, nunca el catálogo entero.
  min_lng := COALESCE(p_min_lng, -3.888);
  min_lat := COALESCE(p_min_lat, 40.348);
  max_lng := COALESCE(p_max_lng, -3.518);
  max_lat := COALESCE(p_max_lat, 40.502);

  IF max_lng <= min_lng OR max_lat <= min_lat THEN
    min_lng := -3.888;
    min_lat := 40.348;
    max_lng := -3.518;
    max_lat := 40.502;
  END IF;

  lim := CASE
    WHEN zoom_i <= 9 THEN 40
    WHEN zoom_i <= 11 THEN 80
    WHEN zoom_i <= 12 THEN 120
    WHEN zoom_i <= 14 THEN 180
    ELSE 220
  END;
  IF COALESCE(p_limit, 0) > 0 AND p_limit < 5000 THEN
    lim := LEAST(lim, GREATEST(p_limit, 20));
  END IF;
  lim := LEAST(lim, 250);

  -- Zoom cercano: fuera polígonos de municipio entero para que entren los locales.
  max_area := CASE WHEN zoom_i >= 13 THEN 15000000 ELSE NULL END;

  simplify_tol := CASE
    WHEN lower(COALESCE(p_layer, '')) = 'landing' THEN 0.0008
    WHEN zoom_i <= 9 THEN 0.0016
    WHEN zoom_i <= 11 THEN 0.001
    WHEN zoom_i <= 12 THEN 0.0006
    WHEN zoom_i >= 16 THEN 0.00004
    WHEN zoom_i >= 14 THEN 0.00012
    ELSE 0.0003
  END;

  WITH picked AS (
    SELECT p.id
    FROM homes.proyecto p
    WHERE (
        p.expediente_grupo IS NOT NULL
        OR p.sigma_layer_kind IS NOT NULL
      )
      AND COALESCE(p.catalog_source, '') IS DISTINCT FROM 'ayuntamiento-portal'
      AND homes._sigma_layer_matches(p.sigma_layer_kind, p_layer)
      AND COALESCE(p.centroid_lat, p.lat) IS NOT NULL
      AND COALESCE(p.centroid_lng, p.lng) IS NOT NULL
      AND (zoom_i >= 13 OR p.has_geometry)
      AND (max_area IS NULL OR COALESCE(p.area_approx_m2, 0) <= max_area)
      AND COALESCE(p.bbox_max_lng, p.centroid_lng, p.lng) >= min_lng
      AND COALESCE(p.bbox_min_lng, p.centroid_lng, p.lng) <= max_lng
      AND COALESCE(p.bbox_max_lat, p.centroid_lat, p.lat) >= min_lat
      AND COALESCE(p.bbox_min_lat, p.centroid_lat, p.lat) <= max_lat
    ORDER BY
      COALESCE(p.area_approx_m2, 0) DESC,
      p.has_geometry DESC,
      p.updated_at DESC NULLS LAST
    LIMIT lim
  )
  SELECT COALESCE(
    jsonb_agg(feat.feature ORDER BY feat.sort_key DESC NULLS LAST, feat.id),
    '[]'::jsonb
  )
  INTO features
  FROM (
    SELECT
      p.id,
      COALESCE(p.area_approx_m2, 0) AS sort_key,
      jsonb_build_object(
        'type', 'Feature',
        'geometry', homes._proyecto_map_geometry(
          p.geom_geojson,
          COALESCE(p.centroid_lng, p.lng),
          COALESCE(p.centroid_lat, p.lat),
          want_poly AND p.has_geometry,
          simplify_tol
        ),
        'properties', jsonb_strip_nulls(jsonb_build_object(
          'id', p.id,
          'EXP_TX_NUMERO', COALESCE(p.exp_numero_original, p.expediente_grupo, p.id),
          'EXP_TX_DENOM', p.denominacion,
          'FIG_TX_ETIQ', p.figura_codigo,
          'TFIG_TX_ABREV', p.tipo_figura,
          'FAS_TX_DENOM', p.fase,
          'ORG_TX_DESC', p.organo_tramitador,
          'ENLACE', p.enlace,
          'Enlace', p.enlace,
          'sigma_layer_kind', p.sigma_layer_kind,
          'FEX_DT_APROB', homes._text_date_ms(p.fecha_aprob),
          'FEX_DT_INFOPUB_INI', homes._text_date_ms(p.infopublica_inicio),
          'FEX_DT_INFOPUB_FIN', homes._text_date_ms(p.infopublica_fin)
        ))
      ) AS feature
    FROM picked pk
    JOIN homes.proyecto p ON p.id = pk.id
  ) feat
  WHERE jsonb_typeof(feat.feature->'geometry') = 'object';

  RETURN jsonb_build_object(
    'type', 'FeatureCollection',
    'generatedAt', now()::text,
    'layer', COALESCE(p_layer, 'ambitos'),
    'zoom', zoom_i,
    'mode', CASE WHEN want_poly THEN 'polygons' ELSE 'points' END,
    'features', COALESCE(features, '[]'::jsonb)
  );
END;
$$;

CREATE OR REPLACE FUNCTION homes.map_cm_portal()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '12s'
AS $$
DECLARE
  lim integer := 200;
  simplify_tol double precision := 0.0006;
  out jsonb;
BEGIN

  WITH base AS (
    SELECT
      p.id,
      COALESCE(p.municipio, p.bocm_municipio, '') AS municipio,
      COALESCE(NULLIF(btrim(p.bocm_title), ''), NULLIF(btrim(p.denominacion), ''), p.id) AS titulo,
      to_char(p.bocm_pub_date, 'YYYY-MM-DD') AS fecha,
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
    WHERE COALESCE(p.catalog_source, '') = 'ayuntamiento-portal'
       OR COALESCE(p.fuente, '') = 'ayuntamiento'
  ),
  props AS (
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
  points AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(p.lng, p.lat)),
      'properties', p.properties
    ) AS feature
    FROM props p
    WHERE p.lat IS NOT NULL AND p.lng IS NOT NULL
      AND p.coord_source IS DISTINCT FROM 'municipio_centroid_jitter'
      AND NOT (
        p.has_geometry
        AND p.geom_geojson IS NOT NULL
        AND jsonb_typeof(p.geom_geojson) = 'object'
        AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
      )
  ),
  poly_ids AS (
    SELECT p.id
    FROM props p
    WHERE p.has_geometry
      AND p.geom_geojson IS NOT NULL
      AND jsonb_typeof(p.geom_geojson) = 'object'
      AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
    ORDER BY p.area_m2 DESC, p.id
    LIMIT lim
  ),
  polys AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', homes._proyecto_map_geometry(
        p.geom_geojson, p.lng, p.lat, true, simplify_tol
      ),
      'properties', p.properties
    ) AS feature
    FROM poly_ids i
    JOIN props p ON p.id = i.id
  )
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'points', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((SELECT jsonb_agg(feature) FROM points), '[]'::jsonb)
    ),
    'polygons', jsonb_build_object(
      'type', 'FeatureCollection',
      'generatedAt', now()::text,
      'features', COALESCE((SELECT jsonb_agg(feature) FROM polys), '[]'::jsonb)
    ),
    'meta', jsonb_build_object(
      'generatedAt', now()::text,
      'proyectosTotal', (SELECT count(*)::int FROM base),
      'proyectosEnMapa', (SELECT count(*)::int FROM points) + (SELECT count(*)::int FROM polys),
      'proyectosPoligonos', (SELECT count(*)::int FROM polys),
      'proyectosPuntosReales', (SELECT count(*)::int FROM points),
      'proyectosSinUbicacion', (
        SELECT count(*)::int FROM base b
        WHERE (b.lat IS NULL OR b.lng IS NULL)
          AND NOT (b.has_geometry AND b.geom_geojson IS NOT NULL)
      )
    )
  )
  INTO out;

  RETURN out;
END;
$$;

CREATE OR REPLACE FUNCTION homes.map_ubicaciones_bbox(
  p_min_lng double precision,
  p_min_lat double precision,
  p_max_lng double precision,
  p_max_lat double precision,
  p_limit integer DEFAULT 800
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '12s'
AS $$
DECLARE
  span double precision;
  lim integer;
  out jsonb;
BEGIN

  span := GREATEST(0, (p_max_lat - p_min_lat) * (p_max_lng - p_min_lng));
  lim := CASE
    WHEN span > 0.02 THEN 600
    WHEN span > 0.004 THEN 1200
    ELSE 2000
  END;
  IF COALESCE(p_limit, 0) > 0 AND p_limit < 5000 THEN
    lim := LEAST(lim, GREATEST(p_limit, 50));
  END IF;
  lim := LEAST(lim, 2200);

  WITH buildings AS (
    SELECT i.id, i.ndp_edificio, i.direccion, i.distrito, i.barrio, i.lat, i.lng
    FROM homes.inmueble i
    WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
      AND i.lat BETWEEN p_min_lat AND p_max_lat
      AND i.lng BETWEEN p_min_lng AND p_max_lng
    LIMIT lim
  ),
  last AS (
    SELECT DISTINCT ON (l.inmueble_id)
      l.inmueble_id,
      l.tipo_expediente,
      l.objeto,
      l.uso,
      l.procedimiento,
      COALESCE(NULLIF(btrim(l.fecha_concesion), ''), l.fecha_alta) AS fecha_raw
    FROM homes.licencia l
    WHERE l.inmueble_id IN (SELECT id FROM buildings)
    ORDER BY
      l.inmueble_id,
      CASE WHEN l.fecha_concesion IS NULL OR btrim(l.fecha_concesion) = '' THEN 1 ELSE 0 END,
      l.fecha_concesion DESC NULLS LAST,
      l.fecha_alta DESC NULLS LAST
  )
  SELECT jsonb_build_object(
    'type', 'FeatureCollection',
    'generatedAt', now()::text,
    'features', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object(
          'type', 'Feature',
          'geometry', jsonb_build_object(
            'type', 'Point',
            'coordinates', jsonb_build_array(b.lng, b.lat)
          ),
          'properties', jsonb_strip_nulls(jsonb_build_object(
            'ndp', b.ndp_edificio,
            'direccion', b.direccion,
            'distrito', b.distrito,
            'barrio', b.barrio,
            'licencias', CASE WHEN last.inmueble_id IS NOT NULL THEN 1 ELSE 0 END,
            'sigma', 0,
            'ultimaLicenciaTipo', last.tipo_expediente,
            'ultimaLicenciaObjeto', last.objeto,
            'ultimaLicenciaUso', last.uso,
            'ultimaLicenciaProcedimiento', last.procedimiento,
            'ultimaLicenciaFecha', CASE
              WHEN last.fecha_raw ~ '^\d{4}-\d{2}-\d{2}' THEN substring(last.fecha_raw FROM 1 FOR 10)
              ELSE last.fecha_raw
            END
          ))
        ))
        FROM buildings b
        LEFT JOIN last ON last.inmueble_id = b.id
      ),
      '[]'::jsonb
    )
  )
  INTO out;

  RETURN COALESCE(out, jsonb_build_object(
    'type', 'FeatureCollection',
    'generatedAt', now()::text,
    'features', '[]'::jsonb
  ));
END;
$$;

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_map_area
  ON homes.proyecto (area_approx_m2 DESC NULLS LAST)
  WHERE has_geometry
    AND COALESCE(centroid_lat, lat) IS NOT NULL;

CREATE OR REPLACE FUNCTION public.map_sigma_geojson(
  p_zoom integer DEFAULT 11,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL,
  p_layer text DEFAULT 'ambitos',
  p_limit integer DEFAULT 80
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '12s'
AS $$
  SELECT homes.map_sigma_geojson(p_zoom, p_min_lng, p_min_lat, p_max_lng, p_max_lat, p_layer, p_limit);
$$;

CREATE OR REPLACE FUNCTION public.map_cm_portal()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '12s'
AS $$ SELECT homes.map_cm_portal(); $$;

CREATE OR REPLACE FUNCTION public.map_ubicaciones_bbox(
  p_min_lng double precision,
  p_min_lat double precision,
  p_max_lng double precision,
  p_max_lat double precision,
  p_limit integer DEFAULT 800
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = homes
SET statement_timeout = '12s'
AS $$
  SELECT homes.map_ubicaciones_bbox(p_min_lng, p_min_lat, p_max_lng, p_max_lat, p_limit);
$$;

GRANT EXECUTE ON FUNCTION homes.map_sigma_geojson(integer, double precision, double precision, double precision, double precision, text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.map_cm_portal() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.map_ubicaciones_bbox(double precision, double precision, double precision, double precision, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_sigma_geojson(integer, double precision, double precision, double precision, double precision, text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_portal() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_ubicaciones_bbox(double precision, double precision, double precision, double precision, integer) TO anon, authenticated, service_role;
