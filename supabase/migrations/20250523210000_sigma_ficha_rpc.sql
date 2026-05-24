-- RPC en public para leer ficha SIGMA + clasificación sin exponer schema homes en PostgREST.

CREATE OR REPLACE FUNCTION homes.get_sigma_clasificacion(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'tipo_legal', v.tipo_legal,
    'escala', v.escala,
    'contenido_principal', v.contenido_principal,
    'fase_normalizada', v.fase_normalizada,
    'categoria_proyecto', v.categoria_proyecto,
    'clasificacion_confianza', v.clasificacion_confianza,
    'clasificacion_fuentes', v.clasificacion_fuentes
  )
  FROM homes.sigma_visor_expediente v
  WHERE v.expediente_grupo = p_expediente_grupo
    AND v.categoria_proyecto IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION homes.get_sigma_ficha(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
DECLARE
  cat jsonb;
  vis jsonb;
  bocm jsonb;
BEGIN
  SELECT jsonb_build_object(
    'expediente_grupo', c.expediente_grupo,
    'exp_numero_original', c.exp_numero_original,
    'sigma_layer_kind', c.sigma_layer_kind,
    'denominacion', c.denominacion,
    'fase', c.fase,
    'fecha_aprob', c.fecha_aprob,
    'infopublica_inicio', c.infopublica_inicio,
    'infopublica_fin', c.infopublica_fin,
    'figura_codigo', c.figura_codigo,
    'tipo_figura', c.tipo_figura,
    'organo_tramitador', c.organo_tramitador,
    'enlace', c.enlace,
    'catalog_source', c.catalog_source,
    'object_id', c.object_id,
    'has_geometry', c.has_geometry,
    'synced_at', c.synced_at
  )
  INTO cat
  FROM homes.sigma_catalog_expediente c
  WHERE c.expediente_grupo = p_expediente_grupo;

  SELECT jsonb_build_object(
    'sin_datos_visor', v.sin_datos_visor,
    'visor_url', v.visor_url,
    'visor_cabecera', v.visor_cabecera,
    'visor_ficha', v.visor_ficha,
    'resumen_contenido', v.resumen_contenido,
    'tipo_legal', v.tipo_legal,
    'escala', v.escala,
    'contenido_principal', v.contenido_principal,
    'fase_normalizada', v.fase_normalizada,
    'categoria_proyecto', v.categoria_proyecto,
    'clasificacion_confianza', v.clasificacion_confianza,
    'clasificacion_fuentes', v.clasificacion_fuentes,
    'tramitacion', v.tramitacion,
    'documentacion_urls', v.documentacion_urls,
    'nti_listado_url', v.nti_listado_url,
    'nti_documentos_total', v.nti_documentos_total,
    'nti_documentos_muestra', v.nti_documentos_muestra,
    'fetched_at', v.fetched_at
  )
  INTO vis
  FROM homes.sigma_visor_expediente v
  WHERE v.expediente_grupo = p_expediente_grupo;

  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'id', p.id,
        'title', left(p.title, 220),
        'bocmDate', p.pub_date,
        'artNum', COALESCE(p.art_num, ''),
        'esRelevante', p.es_relevante
      )
      ORDER BY p.pub_date DESC
    ),
    '[]'::jsonb
  )
  INTO bocm
  FROM (
    SELECT l.project_id
    FROM homes.link_project_sigma l
    WHERE l.expediente_grupo = p_expediente_grupo
    LIMIT 25
  ) links
  JOIN homes.project_boletin p ON p.id = links.project_id;

  IF cat IS NULL AND vis IS NULL AND bocm = '[]'::jsonb THEN
    RETURN NULL;
  END IF;

  RETURN jsonb_build_object(
    'catalog', cat,
    'visor', vis,
    'bocm', bocm
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_sigma_clasificacion(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.get_sigma_clasificacion(p_expediente_grupo);
$$;

CREATE OR REPLACE FUNCTION public.get_sigma_ficha(p_expediente_grupo text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.get_sigma_ficha(p_expediente_grupo);
$$;

GRANT EXECUTE ON FUNCTION homes.get_sigma_clasificacion(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.get_sigma_ficha(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sigma_clasificacion(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sigma_ficha(text) TO anon, authenticated, service_role;
