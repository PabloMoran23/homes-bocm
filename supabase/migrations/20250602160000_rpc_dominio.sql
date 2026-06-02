-- RPCs sobre tablas de dominio (proyecto, licencia, inmueble).

CREATE OR REPLACE FUNCTION homes.get_sigma_clasificacion(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'tipo_legal', p.tipo_legal,
    'escala', p.escala,
    'contenido_principal', p.contenido_principal,
    'fase_normalizada', p.fase_normalizada,
    'categoria_proyecto', p.categoria_proyecto,
    'tipo_obra', p.tipo_obra,
    'clasificacion_confianza', p.clasificacion_confianza,
    'clasificacion_fuentes', p.clasificacion_fuentes
  )
  FROM homes.proyecto p
  WHERE (p.expediente_grupo = p_expediente_grupo OR p.id = p_expediente_grupo)
    AND p.categoria_proyecto IS NOT NULL
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION homes.get_sigma_ficha(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'catalog',
    CASE
      WHEN p.expediente_grupo IS NULL AND p.bocm_primary_id IS NOT NULL THEN NULL
      ELSE jsonb_build_object(
        'expediente_grupo', COALESCE(p.expediente_grupo, p.id),
        'exp_numero_original', p.exp_numero_original,
        'sigma_layer_kind', p.sigma_layer_kind,
        'denominacion', p.denominacion,
        'fase', p.fase,
        'fecha_aprob', p.fecha_aprob,
        'infopublica_inicio', p.infopublica_inicio,
        'infopublica_fin', p.infopublica_fin,
        'figura_codigo', p.figura_codigo,
        'tipo_figura', p.tipo_figura,
        'organo_tramitador', p.organo_tramitador,
        'enlace', p.enlace,
        'catalog_source', p.catalog_source,
        'object_id', p.object_id,
        'has_geometry', p.has_geometry,
        'synced_at', p.sigma_synced_at
      )
    END,
    'visor',
    jsonb_build_object(
      'sin_datos_visor', COALESCE(p.sin_datos_visor, false),
      'visor_url', p.visor_url,
      'visor_cabecera', p.visor_cabecera,
      'visor_ficha', p.visor_ficha,
      'resumen_contenido', p.resumen_contenido,
      'tipo_legal', p.tipo_legal,
      'escala', p.escala,
      'contenido_principal', p.contenido_principal,
      'fase_normalizada', p.fase_normalizada,
      'categoria_proyecto', p.categoria_proyecto,
      'tipo_obra', p.tipo_obra,
      'clasificacion_confianza', p.clasificacion_confianza,
      'clasificacion_fuentes', p.clasificacion_fuentes,
      'tramitacion', COALESCE(p.tramitacion, '[]'::jsonb),
      'documentacion_urls', COALESCE(p.documentacion_urls, '[]'::jsonb),
      'nti_listado_url', p.nti_listado_url,
      'nti_documentos_total', p.nti_documentos_total,
      'nti_documentos_muestra', COALESCE(p.nti_documentos_muestra, '[]'::jsonb),
      'fetched_at', p.visor_fetched_at
    ),
    'bocm',
    COALESCE(
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'id', b.bocm_id,
            'title', left(COALESCE(b.title, ''), 220),
            'bocmDate', b.pub_date,
            'artNum', COALESCE(b.art_num, ''),
            'esRelevante', b.es_relevante
          )
          ORDER BY b.pub_date DESC NULLS LAST, b.es_principal DESC
        )
        FROM homes.proyecto_bocm_publicacion b
        WHERE b.proyecto_id = p.id
      ),
      '[]'::jsonb
    )
  )
  FROM homes.proyecto p
  WHERE p.expediente_grupo = p_expediente_grupo
     OR p.id = p_expediente_grupo
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION homes.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '15s'
AS $$
  WITH inm AS (
    SELECT id, ndp_edificio, direccion, distrito, barrio, lat, lng, coord_source,
           inserted_at, updated_at
    FROM homes.inmueble
    WHERE ndp_edificio = trim(p_ndp)
  ),
  lic AS (
    SELECT
      l.id,
      l.licencia_key,
      l.anio_dataset,
      l.fecha_alta,
      l.fecha_concesion,
      l.procedimiento,
      l.tipo_expediente,
      l.uso,
      l.interesado,
      l.objeto,
      l.unidad
    FROM homes.licencia l
    WHERE l.inmueble_id = (SELECT id FROM inm)
    ORDER BY l.fecha_concesion DESC NULLS LAST, l.fecha_alta DESC
    LIMIT 200
  ),
  lic_total AS (
    SELECT COUNT(*)::int AS n
    FROM homes.licencia l
    WHERE l.inmueble_id = (SELECT id FROM inm)
  ),
  sigma_via_link AS (
    SELECT DISTINCT ON (p.expediente_grupo)
      p.expediente_grupo,
      p.exp_numero_original,
      p.sigma_layer_kind,
      p.denominacion,
      p.fase,
      p.enlace,
      p.fecha_aprob,
      l.proyecto_match_method AS match_method,
      l.proyecto_match_score::double precision AS match_score
    FROM lic
    INNER JOIN homes.licencia l ON l.id = lic.id
    INNER JOIN homes.proyecto p ON p.id = l.proyecto_id
    WHERE p.expediente_grupo IS NOT NULL
    ORDER BY p.expediente_grupo, l.proyecto_match_score DESC NULLS LAST
  ),
  sigma_via_edificio AS (
    SELECT DISTINCT ON (p.expediente_grupo)
      p.expediente_grupo,
      p.exp_numero_original,
      p.sigma_layer_kind,
      p.denominacion,
      p.fase,
      p.enlace,
      p.fecha_aprob,
      'point_in_edificio'::text AS match_method,
      1.0::double precision AS match_score
    FROM inm
    INNER JOIN homes.proyecto p ON p.geom_geojson IS NOT NULL AND p.has_geometry
    WHERE inm.lat IS NOT NULL
      AND inm.lng IS NOT NULL
      AND p.bbox_min_lng <= inm.lng
      AND p.bbox_max_lng >= inm.lng
      AND p.bbox_min_lat <= inm.lat
      AND p.bbox_max_lat >= inm.lat
      AND public.ST_Contains(
        public.ST_SetSRID(public.ST_GeomFromGeoJSON(p.geom_geojson::text), 4326),
        public.ST_SetSRID(public.ST_MakePoint(inm.lng, inm.lat), 4326)
      )
    ORDER BY p.expediente_grupo, p.area_approx_m2 ASC NULLS LAST
  ),
  sigma AS (
    SELECT DISTINCT ON (expediente_grupo)
      expediente_grupo,
      exp_numero_original,
      sigma_layer_kind,
      denominacion,
      fase,
      enlace,
      fecha_aprob,
      match_method,
      match_score
    FROM (
      SELECT * FROM sigma_via_link
      UNION ALL
      SELECT * FROM sigma_via_edificio
    ) merged
    ORDER BY expediente_grupo, match_score DESC NULLS LAST, sigma_layer_kind
  ),
  tram AS (
    SELECT
      s.expediente_grupo,
      COALESCE(p.tramitacion, '[]'::jsonb) AS rows
    FROM sigma s
    INNER JOIN homes.proyecto p ON p.expediente_grupo = s.expediente_grupo
  )
  SELECT CASE
    WHEN NOT EXISTS (SELECT 1 FROM inm) THEN NULL
    ELSE jsonb_build_object(
      'inmueble',
      (SELECT to_jsonb(inm) FROM inm),
      'licencias',
      COALESCE(
        (SELECT jsonb_agg(to_jsonb(lic) ORDER BY lic.fecha_concesion DESC NULLS LAST, lic.fecha_alta DESC) FROM lic),
        '[]'::jsonb
      ),
      'expedientesSigma',
      COALESCE(
        (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.sigma_layer_kind, s.expediente_grupo) FROM sigma s),
        '[]'::jsonb
      ),
      'tramitacionSigma',
      COALESCE(
        (SELECT jsonb_object_agg(t.expediente_grupo, t.rows) FROM tram t),
        '{}'::jsonb
      ),
      'stats',
      jsonb_build_object(
        'licenciasTotal', (SELECT n FROM lic_total),
        'expedientesSigma', (SELECT COUNT(*)::int FROM sigma)
      )
    )
  END;
$$;

-- boletin_area: licencia + proyecto (geom en fila proyecto)
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
  SELECT ranked.id, ranked.ndp_edificio, ranked.direccion, ranked.distrito, ranked.lat, ranked.lng, ranked.distancia_m
  FROM (
    SELECT
      i.id, i.ndp_edificio, i.direccion, i.distrito, i.lat, i.lng,
      round(homes.haversine_m(p.center_lng, p.center_lat, i.lng, i.lat))::int AS distancia_m
    FROM homes.inmueble i
    CROSS JOIN params p
    WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
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
    COALESCE(l.fecha_concesion, l.fecha_alta) AS fecha,
    b.distancia_m AS "distanciaM",
    LEFT(COALESCE(l.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
    LEFT(CONCAT_WS(' · ', l.uso, l.procedimiento, b.direccion), 200) AS detalle,
    b.ndp_edificio AS ndp, b.direccion, b.distrito, b.lat, b.lng,
    COALESCE(homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta), DATE '1900-01-01') AS fecha_sort
  FROM homes.licencia l
  INNER JOIN buildings_in_radius b ON b.id = l.inmueble_id
  CROSS JOIN params p
  WHERE homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta) IS NULL
     OR homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta) >= p.cutoff
  ORDER BY COALESCE(homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta), DATE '1900-01-01') DESC
  LIMIT 151
),
lic_orphan AS (
  SELECT
    'licencia' AS tipo,
    COALESCE(l.fecha_concesion, l.fecha_alta) AS fecha,
    round(homes.haversine_m(p.center_lng, p.center_lat, l.lng, l.lat))::int AS "distanciaM",
    LEFT(COALESCE(l.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
    LEFT(CONCAT_WS(' · ', l.uso, l.procedimiento, NULL), 200) AS detalle,
    NULL::text AS ndp, NULL::text AS direccion, NULL::text AS distrito,
    l.lat, l.lng,
    COALESCE(homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta), DATE '1900-01-01') AS fecha_sort
  FROM homes.licencia l
  CROSS JOIN params p
  WHERE l.inmueble_id IS NULL
    AND l.lat IS NOT NULL AND l.lng IS NOT NULL
    AND l.lat BETWEEN p.min_lat AND p.max_lat
    AND l.lng BETWEEN p.min_lng AND p.max_lng
    AND homes.haversine_m(p.center_lng, p.center_lat, l.lng, l.lat) <= p.radius_m
    AND (
      homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta) IS NULL
      OR homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta) >= p.cutoff
    )
  ORDER BY COALESCE(homes.boletin_fecha_licencia(l.fecha_concesion, l.fecha_alta), DATE '1900-01-01') DESC
  LIMIT 21
),
lic_pool AS (
  SELECT * FROM lic_linked
  UNION ALL
  SELECT * FROM lic_orphan
),
lic_stats AS (
  SELECT
    CASE WHEN (SELECT count(*)::int FROM lic_linked) >= 151 THEN 150 ELSE (SELECT count(*)::int FROM lic_pool) END AS n,
    (SELECT count(*)::int FROM lic_linked) >= 151 AS capped
),
lic_map AS (
  SELECT * FROM lic_pool ORDER BY fecha_sort DESC LIMIT 25
),
sigma_ranked AS (
  SELECT
    'sigma' AS tipo,
    COALESCE(p.fecha_aprob, '01/01/' || split_part(p.exp_numero_original, '/', 2)) AS fecha,
    dist.distancia_m AS "distanciaM",
    LEFT(COALESCE(p.denominacion, p.expediente_grupo, p.id), 140) AS titulo,
    LEFT(CONCAT_WS(' · ', p.fase, 'A ' || dist.distancia_m::text || ' m'), 200) AS detalle,
    COALESCE(p.expediente_grupo, p.id) AS "expedienteGrupo",
    false AS "contienePunto",
    p.sigma_layer_kind AS "sigmaLayerKind",
    p.centroid_lat AS lat,
    p.centroid_lng AS lng,
    COALESCE(
      CASE WHEN p.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN p.fecha_aprob::date ELSE NULL END,
      DATE '2000-01-01'
    ) AS fecha_sort
  FROM homes.proyecto p
  CROSS JOIN params par
  CROSS JOIN LATERAL (
    SELECT round(homes.haversine_m(par.center_lng, par.center_lat, p.centroid_lng, p.centroid_lat))::int AS distancia_m
  ) dist
  WHERE p.centroid_lat IS NOT NULL
    AND p.centroid_lng IS NOT NULL
    AND p.has_geometry
    AND p.bbox_max_lng >= par.min_lng
    AND p.bbox_min_lng <= par.max_lng
    AND p.bbox_max_lat >= par.min_lat
    AND p.bbox_min_lat <= par.max_lat
    AND dist.distancia_m <= par.radius_m
    AND COALESCE(
      CASE WHEN p.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN p.fecha_aprob::date ELSE NULL END,
      DATE '2000-01-01'
    ) >= par.cutoff
  ORDER BY COALESCE(
    CASE WHEN p.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN p.fecha_aprob::date ELSE NULL END,
    DATE '2000-01-01'
  ) DESC
  LIMIT 81
),
sigma_stats AS (
  SELECT LEAST(count(*)::int, 80) AS n, count(*) >= 81 AS capped FROM sigma_ranked
),
sigma_map AS (
  SELECT * FROM sigma_ranked ORDER BY fecha_sort DESC LIMIT 20
),
timeline_rows AS (
  SELECT * FROM (
    SELECT lp.tipo, lp.fecha, lp."distanciaM", lp.titulo, lp.detalle, lp.ndp, lp.direccion, lp.distrito,
      NULL::text AS "expedienteGrupo", NULL::boolean AS "contienePunto", NULL::text AS "sigmaLayerKind",
      lp.lat, lp.lng, lp.fecha_sort
    FROM lic_pool lp ORDER BY lp.fecha_sort DESC LIMIT 40
  ) lic_part
  UNION ALL
  SELECT * FROM (
    SELECT sr.tipo, sr.fecha, sr."distanciaM", sr.titulo, sr.detalle, NULL::text AS ndp, NULL::text AS direccion,
      NULL::text AS distrito, sr."expedienteGrupo", sr."contienePunto", sr."sigmaLayerKind", sr.lat, sr.lng, sr.fecha_sort
    FROM sigma_ranked sr ORDER BY sr.fecha_sort DESC LIMIT 40
  ) sigma_part
),
timeline_ordered AS (
  SELECT * FROM timeline_rows ORDER BY fecha_sort DESC LIMIT 80
)
SELECT jsonb_build_object(
  'center', jsonb_build_object(
    'lat', p.center_lat, 'lng', p.center_lng,
    'ndp', c.ndp_edificio, 'direccion', c.direccion, 'distrito', c.distrito, 'barrio', c.barrio
  ),
  'params', jsonb_build_object('radiusM', p.radius_m::int, 'months', p.months_i),
  'stats', jsonb_build_object(
    'licencias', (SELECT n FROM lic_stats),
    'expedientesSigma', (SELECT n FROM sigma_stats),
    'eventos', (SELECT count(*)::int FROM timeline_ordered),
    'licenciasCapped', COALESCE((SELECT capped FROM lic_stats), false),
    'expedientesSigmaCapped', COALESCE((SELECT capped FROM sigma_stats), false)
  ),
  'licencias', COALESCE((SELECT jsonb_agg(to_jsonb(lm) - 'fecha_sort' ORDER BY lm.fecha_sort DESC) FROM lic_map lm), '[]'::jsonb),
  'expedientesSigma', COALESCE((SELECT jsonb_agg(to_jsonb(sm) - 'fecha_sort' ORDER BY sm.fecha_sort DESC) FROM sigma_map sm), '[]'::jsonb),
  'timeline', COALESCE((SELECT jsonb_agg(to_jsonb(tr) - 'fecha_sort' ORDER BY tr.fecha_sort DESC) FROM timeline_ordered tr), '[]'::jsonb)
)
FROM params p
LEFT JOIN center_pick c ON true;
$$;

CREATE OR REPLACE FUNCTION homes.list_proyectos_madrid(p_limit integer DEFAULT 5000)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', COALESCE(MAX(p.sigma_synced_at), now())::text,
    'expedientes', COALESCE(
      jsonb_agg(
        jsonb_build_object(
          'source', COALESCE(p.catalog_source, p.sigma_layer_kind, 'tramitados_ad'),
          'EXP_TX_NUMERO', COALESCE(p.exp_numero_original, p.expediente_grupo, p.id),
          'EXP_TX_DENOM', p.denominacion,
          'FAS_TX_DENOM', p.fase,
          'FEX_DT_INFOPUB_INI', p.infopublica_inicio,
          'FEX_DT_INFOPUB_FIN', p.infopublica_fin,
          'FEX_DT_APROB', p.fecha_aprob,
          'FIG_TX_ETIQ', p.figura_codigo,
          'TFIG_TX_ABREV', p.tipo_figura,
          'ORG_TX_DESC', p.organo_tramitador,
          'EXP_ID', p.object_id,
          'Enlace', p.enlace,
          'sigma_layer_kind', p.sigma_layer_kind,
          'has_geometry', p.has_geometry
        )
        ORDER BY p.expediente_grupo NULLS LAST, p.id
      ),
      '[]'::jsonb
    ),
    'counts', jsonb_build_object(
      'total', COUNT(*)::int,
      'with_geometry', COUNT(*) FILTER (WHERE p.has_geometry)::int,
      'expedientes_unicos', COUNT(DISTINCT COALESCE(p.expediente_grupo, p.id))::int
    )
  )
  FROM (
    SELECT *
    FROM homes.proyecto
    WHERE expediente_grupo IS NOT NULL
       OR sigma_layer_kind IS NOT NULL
       OR bocm_municipio ILIKE 'madrid'
    ORDER BY COALESCE(sigma_synced_at, updated_at) DESC NULLS LAST
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 5000), 100), 8000)
  ) p;
$$;

CREATE OR REPLACE FUNCTION homes.list_sigma_clasificacion()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT COALESCE(
    jsonb_object_agg(
      p.expediente_grupo,
      jsonb_build_object(
        'tipoLegal', p.tipo_legal,
        'escala', p.escala,
        'contenidoPrincipal', p.contenido_principal,
        'faseNormalizada', p.fase_normalizada,
        'categoriaProyecto', p.categoria_proyecto,
        'tipoObra', p.tipo_obra,
        'confianza', p.clasificacion_confianza
      )
    ),
    '{}'::jsonb
  )
  FROM homes.proyecto p
  WHERE p.expediente_grupo IS NOT NULL
    AND p.categoria_proyecto IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION homes.get_proyecto_portal(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT to_jsonb(p) - 'visor_raw_json' - 'raw_features_json' - 'metrics_json' - 'hechos_json' - 'fuentes_pdf_json'
  FROM homes.proyecto p
  WHERE p.bocm_primary_id = trim(p_id)
     OR p.id = trim(p_id)
     OR p.id = 'bocm:' || trim(p_id)
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.get_proyecto_portal(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.get_proyecto_portal(p_id);
$$;

CREATE OR REPLACE FUNCTION public.list_proyectos_madrid(p_limit integer DEFAULT 5000)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.list_proyectos_madrid(p_limit);
$$;

CREATE OR REPLACE FUNCTION public.list_sigma_clasificacion()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.list_sigma_clasificacion();
$$;

GRANT EXECUTE ON FUNCTION homes.get_proyecto_portal(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.list_proyectos_madrid(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.list_sigma_clasificacion() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_proyecto_portal(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_proyectos_madrid(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_sigma_clasificacion() TO anon, authenticated, service_role;

ANALYZE homes.proyecto;
ANALYZE homes.licencia;
ANALYZE homes.inmueble;
