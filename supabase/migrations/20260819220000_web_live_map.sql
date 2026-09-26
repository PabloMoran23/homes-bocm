-- Lectura en vivo para la web: mapa por puntos / bbox, stats y ficheros auxiliares.
-- No volcar geom_geojson completo: polígonos solo simplificados y en recorte.

CREATE OR REPLACE FUNCTION homes._text_date_ms(p_raw text)
RETURNS bigint
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  IF p_raw IS NULL OR btrim(p_raw) = '' THEN
    RETURN NULL;
  END IF;
  IF p_raw ~ '^\d{4}-\d{2}-\d{2}' THEN
    RETURN (extract(epoch FROM substring(p_raw FROM 1 FOR 10)::date)::bigint) * 1000;
  END IF;
  IF p_raw ~ '^\d{1,2}/\d{1,2}/\d{4}' THEN
    RETURN (extract(epoch FROM to_date(btrim(p_raw), 'DD/MM/YYYY'))::bigint) * 1000;
  END IF;
  RETURN NULL;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION homes._text_year(p_raw text, p_fallback integer)
RETURNS integer
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  IF p_raw ~ '^\d{4}-\d{2}-\d{2}' THEN
    RETURN substring(p_raw FROM 1 FOR 4)::integer;
  END IF;
  IF p_raw ~ '^\d{1,2}/\d{1,2}/\d{4}' THEN
    RETURN substring(p_raw FROM '\d{4}$')::integer;
  END IF;
  RETURN p_fallback;
EXCEPTION WHEN OTHERS THEN
  RETURN p_fallback;
END;
$$;

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
        IF COALESCE(p_simplify, 0) > 0 THEN
          simplified := public.ST_SimplifyPreserveTopology(g, p_simplify);
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

CREATE OR REPLACE FUNCTION homes._sigma_layer_matches(p_kind text, p_layer text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE lower(COALESCE(p_layer, 'ambitos'))
    WHEN 'ambitos' THEN true
    WHEN 'landing' THEN true
    WHEN 'ip' THEN COALESCE(p_kind, '') IN ('informacion_publica', 'ip')
    WHEN 'ad' THEN COALESCE(p_kind, '') IN ('tramitados_ad', 'ad')
    WHEN 'gestion' THEN COALESCE(p_kind, '') IN ('gestion', 'tramitados_gestion')
    WHEN 'urbanizacion' THEN COALESCE(p_kind, '') IN ('urbanizacion', 'tramitados_urbanizacion')
    ELSE true
  END;
$$;

CREATE OR REPLACE FUNCTION homes.map_sigma_geojson(
  p_zoom integer DEFAULT 11,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL,
  p_layer text DEFAULT 'ambitos',
  p_limit integer DEFAULT 6000
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
DECLARE
  zoom_i integer := LEAST(GREATEST(COALESCE(p_zoom, 11), 1), 22);
  lim integer := LEAST(GREATEST(COALESCE(p_limit, 6000), 50), 8000);
  want_poly boolean;
  simplify_tol double precision;
  bbox_ok boolean;
  features jsonb;
BEGIN
  PERFORM set_config('statement_timeout', '12000', true);

  bbox_ok :=
    p_min_lng IS NOT NULL AND p_min_lat IS NOT NULL
    AND p_max_lng IS NOT NULL AND p_max_lat IS NOT NULL
    AND p_max_lng > p_min_lng AND p_max_lat > p_min_lat;

  want_poly := true;

  -- Zoom amplio: pocos ámbitos grandes, geometría tosca.
  -- Zoom cercano: más polígonos del recorte, más detalle.
  IF COALESCE(p_limit, 0) <= 0 OR p_limit >= 6000 THEN
    lim := CASE
      WHEN zoom_i <= 9 THEN 70
      WHEN zoom_i <= 11 THEN 110
      WHEN zoom_i <= 12 THEN 160
      ELSE 400
    END;
  ELSE
    lim := LEAST(GREATEST(p_limit, 40), CASE WHEN zoom_i <= 12 THEN 220 ELSE 450 END);
  END IF;

  simplify_tol := CASE
    WHEN lower(COALESCE(p_layer, '')) = 'landing' THEN 0.0007
    WHEN zoom_i <= 9 THEN 0.0014
    WHEN zoom_i <= 11 THEN 0.0009
    WHEN zoom_i <= 12 THEN 0.00055
    WHEN zoom_i >= 16 THEN 0.00003
    WHEN zoom_i >= 14 THEN 0.0001
    ELSE 0.00028
  END;

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
      AND (
        NOT bbox_ok
        OR (
          COALESCE(p.bbox_max_lng, p.centroid_lng, p.lng) >= p_min_lng
          AND COALESCE(p.bbox_min_lng, p.centroid_lng, p.lng) <= p_max_lng
          AND COALESCE(p.bbox_max_lat, p.centroid_lat, p.lat) >= p_min_lat
          AND COALESCE(p.bbox_min_lat, p.centroid_lat, p.lat) <= p_max_lat
        )
      )
    ORDER BY
      COALESCE(p.area_approx_m2, 0) DESC,
      p.has_geometry DESC,
      p.updated_at DESC NULLS LAST
    LIMIT lim
  ) feat
  WHERE jsonb_typeof(feat.feature->'geometry') = 'object';

  RETURN jsonb_build_object(
    'type', 'FeatureCollection',
    'generatedAt', now()::text,
    'layer', COALESCE(p_layer, 'ambitos'),
    'zoom', zoom_i,
    'mode', CASE WHEN want_poly THEN 'polygons' ELSE 'points' END,
    'features', features
  );
END;
$$;

CREATE OR REPLACE FUNCTION homes.map_cm_portal()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
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
      COALESCE(p.centroid_lat, p.lat) AS lat
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
  polys AS (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', p.geom_geojson,
      'properties', p.properties
    ) AS feature
    FROM props p
    WHERE p.has_geometry
      AND p.geom_geojson IS NOT NULL
      AND jsonb_typeof(p.geom_geojson) = 'object'
      AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
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
  );
$$;

CREATE OR REPLACE FUNCTION homes.map_ubicaciones_bbox(
  p_min_lng double precision,
  p_min_lat double precision,
  p_max_lng double precision,
  p_max_lat double precision,
  p_limit integer DEFAULT 4000
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  WITH buildings AS (
    SELECT i.id, i.ndp_edificio, i.direccion, i.distrito, i.barrio, i.lat, i.lng
    FROM homes.inmueble i
    WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
      AND i.lat BETWEEN p_min_lat AND p_max_lat
      AND i.lng BETWEEN p_min_lng AND p_max_lng
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 4000), 50), 6000)
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
  );
$$;

CREATE OR REPLACE FUNCTION homes.search_ubicaciones(
  p_q text,
  p_limit integer DEFAULT 12
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT COALESCE(
    jsonb_agg(jsonb_build_object(
      'ndp', s.ndp_edificio,
      'direccion', COALESCE(s.direccion, ''),
      'distrito', COALESCE(s.distrito, ''),
      'barrio', COALESCE(s.barrio, ''),
      'label', COALESCE(NULLIF(btrim(s.direccion), ''), s.ndp_edificio),
      'lat', s.lat,
      'lng', s.lng
    )),
    '[]'::jsonb
  )
  FROM (
    SELECT i.ndp_edificio, i.direccion, i.distrito, i.barrio, i.lat, i.lng
    FROM homes.inmueble i
    WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
      AND length(btrim(COALESCE(p_q, ''))) >= 2
      AND (
        i.ndp_edificio ILIKE '%' || btrim(p_q) || '%'
        OR COALESCE(i.direccion, '') ILIKE '%' || btrim(p_q) || '%'
        OR COALESCE(i.distrito, '') ILIKE '%' || btrim(p_q) || '%'
        OR COALESCE(i.barrio, '') ILIKE '%' || btrim(p_q) || '%'
      )
    ORDER BY
      CASE WHEN i.ndp_edificio ILIKE btrim(p_q) THEN 0 ELSE 1 END,
      CASE WHEN COALESCE(i.direccion, '') ILIKE btrim(p_q) || '%' THEN 0 ELSE 1 END,
      i.ndp_edificio
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 12), 1), 25)
  ) s;
$$;

CREATE OR REPLACE FUNCTION homes.list_sigma_metrics()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'count', count(*)::int,
    'byExpediente', COALESCE(
      jsonb_object_agg(
        p.expediente_grupo,
        jsonb_strip_nulls(jsonb_build_object(
          'num_viviendas_max', COALESCE(p.metric_num_viviendas_max, p.num_viviendas_max),
          'sup_total_m2', COALESCE(p.metric_sup_total_m2, p.sup_total_m2),
          'sup_edificable_m2', COALESCE(p.metric_sup_edificable_m2, p.sup_edificable_m2),
          'tipo_vivienda', COALESCE(p.tipo_vivienda, p.bocm_tipo_vivienda),
          'genera_vivienda_nueva', p.genera_vivienda_nueva,
          'familia_expediente', p.familia_expediente,
          'pdfs_procesados', p.pdfs_procesados,
          'doc_role_principal', p.doc_role_principal,
          'hechos', '[]'::jsonb
        ))
      ),
      '{}'::jsonb
    )
  )
  FROM homes.proyecto p
  WHERE p.expediente_grupo IS NOT NULL
    AND (
      COALESCE(p.metric_num_viviendas_max, p.num_viviendas_max) IS NOT NULL
      OR COALESCE(p.metric_sup_total_m2, p.sup_total_m2) IS NOT NULL
      OR p.genera_vivienda_nueva IS NOT NULL
      OR COALESCE(p.pdfs_procesados, 0) > 0
    );
$$;

CREATE OR REPLACE FUNCTION homes.list_sigma_map_cards()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'byExpediente', COALESCE(
      jsonb_object_agg(
        p.expediente_grupo,
        jsonb_strip_nulls(jsonb_build_object(
          'distrito', COALESCE(p.visor_ficha->>'distrito', p.visor_ficha->>'Distrito'),
          'ambitoLabel', COALESCE(
            NULLIF(p.visor_ficha->>'ambitoOrdenacion', ''),
            NULLIF(p.visor_ficha->>'descripcionAmbito', ''),
            p.denominacion
          ),
          'resumen', COALESCE(
            NULLIF(p.resumen_contenido, ''),
            NULLIF(p.visor_ficha->>'resumenContenido', ''),
            left(COALESCE(p.denominacion, ''), 280)
          )
        ))
      ),
      '{}'::jsonb
    )
  )
  FROM homes.proyecto p
  WHERE p.expediente_grupo IS NOT NULL
    AND (
      p.visor_ficha IS NOT NULL
      OR NULLIF(p.resumen_contenido, '') IS NOT NULL
      OR NULLIF(p.denominacion, '') IS NOT NULL
    );
$$;

CREATE OR REPLACE FUNCTION homes.madrid_dashboard_stats()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
DECLARE
  out jsonb;
  lic jsonb;
  sig jsonb;
BEGIN
  PERFORM set_config('statement_timeout', '8000', true);

  -- Licencias (~170k) no se agregan aquí: el dashboard mezcla este bloque
  -- con el snapshot estático. El mapa las pide por bbox.
  lic := jsonb_build_object(
    'generatedAt', now()::text,
    'totalRows', NULL,
    'withCoords', NULL,
    'years', '[]'::jsonb,
    'seriesByYear', '[]'::jsonb,
    'topUso', '[]'::jsonb,
    'topDistrito', '[]'::jsonb,
    'topProcedimiento', '[]'::jsonb,
    'topTipoExpediente', '[]'::jsonb
  );


  SELECT jsonb_build_object(
    'total', count(*)::int,
    'conVisorFicha', count(*) FILTER (WHERE p.visor_fetched_at IS NOT NULL)::int,
    'conTramitacion', count(*) FILTER (WHERE p.visor_fetched_at IS NOT NULL)::int,
    'conGeometry', count(*) FILTER (WHERE p.has_geometry)::int,
    'conMetricasPdf', count(*) FILTER (WHERE COALESCE(p.pdfs_procesados, 0) > 0)::int,
    'viviendasEnMetricas', COALESCE(sum(COALESCE(p.metric_num_viviendas_max, p.num_viviendas_max)) FILTER (
      WHERE COALESCE(p.metric_num_viviendas_max, p.num_viviendas_max) IS NOT NULL
    ), 0)::int,
    'expedientesConViviendas', count(*) FILTER (
      WHERE COALESCE(p.metric_num_viviendas_max, p.num_viviendas_max) IS NOT NULL
    )::int,
    'conClasificacion', count(*) FILTER (WHERE NULLIF(p.categoria_proyecto, '') IS NOT NULL)::int,
    'seriesByYear', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('year', s.y, 'count', s.n) ORDER BY s.y)
        FROM (
          SELECT NULLIF(split_part(p2.expediente_grupo, '/', 2), '')::int AS y, count(*)::int AS n
          FROM homes.proyecto p2
          WHERE p2.expediente_grupo IS NOT NULL
            AND split_part(p2.expediente_grupo, '/', 2) ~ '^\d{4}$'
          GROUP BY 1
        ) s
        WHERE s.y IS NOT NULL
      ),
      '[]'::jsonb
    ),
    'byCategoriaProyecto', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT p2.categoria_proyecto AS n, count(*)::int AS c
          FROM homes.proyecto p2
          WHERE NULLIF(p2.categoria_proyecto, '') IS NOT NULL
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'byTipoObra', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT p2.tipo_obra AS n, count(*)::int AS c
          FROM homes.proyecto p2
          WHERE NULLIF(p2.tipo_obra, '') IS NOT NULL
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'byFase', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(p2.fase, ''), '(sin fase)') AS n, count(*)::int AS c
          FROM homes.proyecto p2
          WHERE p2.expediente_grupo IS NOT NULL OR p2.sigma_layer_kind IS NOT NULL
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'byFiguraTipo', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(p2.figura_codigo, ''), '(sin figura)') AS n, count(*)::int AS c
          FROM homes.proyecto p2
          WHERE p2.expediente_grupo IS NOT NULL OR p2.sigma_layer_kind IS NOT NULL
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'byLayer', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(p2.sigma_layer_kind, ''), '(sin capa)') AS n, count(*)::int AS c
          FROM homes.proyecto p2
          WHERE p2.expediente_grupo IS NOT NULL OR p2.sigma_layer_kind IS NOT NULL
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'topViviendas', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object(
          'expedienteGrupo', t.expediente_grupo,
          'viviendas', t.v,
          'supM2', t.s
        ) ORDER BY t.v DESC)
        FROM (
          SELECT
            p2.expediente_grupo,
            COALESCE(p2.metric_num_viviendas_max, p2.num_viviendas_max)::int AS v,
            COALESCE(p2.metric_sup_total_m2, p2.sup_total_m2) AS s
          FROM homes.proyecto p2
          WHERE p2.expediente_grupo IS NOT NULL
            AND COALESCE(p2.metric_num_viviendas_max, p2.num_viviendas_max) IS NOT NULL
          ORDER BY v DESC NULLS LAST
          LIMIT 15
        ) t
      ),
      '[]'::jsonb
    )
  )
  INTO sig
  FROM homes.proyecto p
  WHERE p.expediente_grupo IS NOT NULL OR p.sigma_layer_kind IS NOT NULL;

  out := jsonb_build_object(
    'generatedAt', now()::text,
    'licencias', lic,
    'sigma', sig
  );
  RETURN out;
END;
$$;

CREATE OR REPLACE FUNCTION homes.web_summary()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'total', (SELECT count(*)::int FROM homes.proyecto),
    'dateRange', jsonb_build_object(
      'min', (SELECT to_char(min(bocm_pub_date), 'YYYY-MM-DD') FROM homes.proyecto),
      'max', (SELECT to_char(max(bocm_pub_date), 'YYYY-MM-DD') FROM homes.proyecto)
    ),
    'byMunicipio', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(municipio, ''), NULLIF(bocm_municipio, ''), '(sin municipio)') AS n,
                 count(*)::int AS c
          FROM homes.proyecto
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 30
        ) t
      ),
      '[]'::jsonb
    ),
    'byTipo', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(bocm_tipo_instrumento, ''), NULLIF(sigma_layer_kind, ''), '(otro)') AS n,
                 count(*)::int AS c
          FROM homes.proyecto
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 20
        ) t
      ),
      '[]'::jsonb
    ),
    'byYear', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('year', t.y::text, 'count', t.c) ORDER BY t.y)
        FROM (
          SELECT extract(year FROM bocm_pub_date)::int AS y, count(*)::int AS c
          FROM homes.proyecto
          WHERE bocm_pub_date IS NOT NULL
          GROUP BY 1
        ) t
      ),
      '[]'::jsonb
    ),
    'byTerritorio', jsonb_build_array(jsonb_build_object('name', 'comunidad-madrid', 'count', (SELECT count(*)::int FROM homes.proyecto))),
    'bySource', COALESCE(
      (
        SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
        FROM (
          SELECT COALESCE(NULLIF(fuente, ''), NULLIF(catalog_source, ''), 'desconocido') AS n,
                 count(*)::int AS c
          FROM homes.proyecto
          GROUP BY 1
          ORDER BY c DESC
          LIMIT 15
        ) t
      ),
      '[]'::jsonb
    ),
    'withCoords', (
      SELECT count(*)::int FROM homes.proyecto
      WHERE COALESCE(lat, centroid_lat) IS NOT NULL
    ),
    'portal', jsonb_build_object('name', 'Homes', 'tagline', 'Urbanismo de Madrid')
  );
$$;

CREATE OR REPLACE FUNCTION public.map_sigma_geojson(
  p_zoom integer DEFAULT 11,
  p_min_lng double precision DEFAULT NULL,
  p_min_lat double precision DEFAULT NULL,
  p_max_lng double precision DEFAULT NULL,
  p_max_lat double precision DEFAULT NULL,
  p_layer text DEFAULT 'ambitos',
  p_limit integer DEFAULT 6000
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$
  SELECT homes.map_sigma_geojson(p_zoom, p_min_lng, p_min_lat, p_max_lng, p_max_lat, p_layer, p_limit);
$$;

CREATE OR REPLACE FUNCTION public.map_cm_portal()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.map_cm_portal(); $$;

CREATE OR REPLACE FUNCTION public.map_ubicaciones_bbox(
  p_min_lng double precision,
  p_min_lat double precision,
  p_max_lng double precision,
  p_max_lat double precision,
  p_limit integer DEFAULT 4000
) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$
  SELECT homes.map_ubicaciones_bbox(p_min_lng, p_min_lat, p_max_lng, p_max_lat, p_limit);
$$;

CREATE OR REPLACE FUNCTION public.search_ubicaciones(p_q text, p_limit integer DEFAULT 12)
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.search_ubicaciones(p_q, p_limit); $$;

CREATE OR REPLACE FUNCTION public.list_sigma_metrics()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.list_sigma_metrics(); $$;

CREATE OR REPLACE FUNCTION public.list_sigma_map_cards()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.list_sigma_map_cards(); $$;

CREATE OR REPLACE FUNCTION public.madrid_dashboard_stats()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.madrid_dashboard_stats(); $$;

CREATE OR REPLACE FUNCTION public.web_summary()
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.web_summary(); $$;

GRANT EXECUTE ON FUNCTION homes.map_sigma_geojson(integer, double precision, double precision, double precision, double precision, text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.map_cm_portal() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.map_ubicaciones_bbox(double precision, double precision, double precision, double precision, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.search_ubicaciones(text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.list_sigma_metrics() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.list_sigma_map_cards() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.madrid_dashboard_stats() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.web_summary() TO anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.map_sigma_geojson(integer, double precision, double precision, double precision, double precision, text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_cm_portal() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.map_ubicaciones_bbox(double precision, double precision, double precision, double precision, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.search_ubicaciones(text, integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_sigma_metrics() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_sigma_map_cards() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.madrid_dashboard_stats() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.web_summary() TO anon, authenticated, service_role;

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_centroid
  ON homes.proyecto (centroid_lng, centroid_lat)
  WHERE centroid_lat IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_homes_proyecto_catalog_source
  ON homes.proyecto (catalog_source);
