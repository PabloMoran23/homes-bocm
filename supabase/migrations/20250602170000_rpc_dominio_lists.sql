-- Listados agregados para sustituir JSON estático en /explore.

CREATE OR REPLACE FUNCTION homes.list_sigma_bocm_by_expediente()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'byExpediente', COALESCE(
      (
        SELECT jsonb_object_agg(sub.expediente_grupo, sub.links)
        FROM (
          SELECT
            p.expediente_grupo,
            jsonb_agg(
              jsonb_build_object(
                'id', b.bocm_id,
                'title', left(COALESCE(b.title, p.bocm_title, ''), 220),
                'bocmDate', COALESCE(to_char(b.pub_date, 'YYYY-MM-DD'), ''),
                'artNum', COALESCE(b.art_num, ''),
                'esRelevante', b.es_relevante
              )
              ORDER BY b.pub_date DESC NULLS LAST, b.es_principal DESC
            ) AS links
          FROM homes.proyecto p
          INNER JOIN homes.proyecto_bocm_publicacion b ON b.proyecto_id = p.id
          WHERE p.expediente_grupo IS NOT NULL
          GROUP BY p.expediente_grupo
        ) sub
      ),
      '{}'::jsonb
    )
  );
$$;

CREATE OR REPLACE FUNCTION homes.list_proyectos_bocm_madrid()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT jsonb_build_object(
    'generatedAt', COALESCE(MAX(p.updated_at), now())::text,
    'projects', COALESCE(
      jsonb_agg(
        to_jsonb(p)
          - 'visor_raw_json'
          - 'raw_features_json'
          - 'metrics_json'
          - 'hechos_json'
          - 'fuentes_pdf_json'
          - 'geom_geojson'
          - 'tramitacion'
          - 'documentacion_urls'
          - 'nti_documentos_muestra'
          - 'visor_ficha'
          - 'visor_cabecera'
          - 'clasificacion_fuentes'
        ORDER BY p.bocm_pub_date DESC NULLS LAST, p.bocm_primary_id
      ),
      '[]'::jsonb
    )
  )
  FROM homes.proyecto p
  WHERE p.bocm_primary_id IS NOT NULL
    AND lower(trim(COALESCE(p.bocm_municipio, p.municipio, ''))) IN (
      'madrid',
      'madrid capital',
      'madrid, capital'
    );
$$;

CREATE OR REPLACE FUNCTION public.list_sigma_bocm_by_expediente()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.list_sigma_bocm_by_expediente();
$$;

CREATE OR REPLACE FUNCTION public.list_proyectos_bocm_madrid()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
  SELECT homes.list_proyectos_bocm_madrid();
$$;

GRANT EXECUTE ON FUNCTION homes.list_sigma_bocm_by_expediente() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.list_proyectos_bocm_madrid() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_sigma_bocm_by_expediente() TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.list_proyectos_bocm_madrid() TO anon, authenticated, service_role;
