-- The stored list_proyectos_madrid payload is 2.2 MB of JSON text.
-- Next's data cache refuses entries whose JSON.stringify size is over
-- 2 MB, so the ficha and /api/dominio/madrid-sigma fetches are never
-- cached. Almost all of the extra weight is null keys repeated on every
-- expediente (the values themselves are about 1 MB).
--
-- The reader strips nulls immediately, which brings the current production
-- payload to about 1.74 MB of JSON and about 1.91 MB once Next escapes it.
-- The compute function stores that smaller shape on the next portal cron
-- and stops reading toasted columns. This migration does not refresh.

CREATE OR REPLACE FUNCTION homes.compute_list_proyectos_madrid(p_limit integer DEFAULT 8000)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '90s'
AS $$
  SELECT jsonb_build_object(
    'generatedAt', COALESCE(MAX(p.sigma_synced_at), now())::text,
    'expedientes', COALESCE(
      jsonb_agg(
        jsonb_strip_nulls(jsonb_build_object(
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
        ))
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
    SELECT
      catalog_source,
      sigma_layer_kind,
      exp_numero_original,
      expediente_grupo,
      id,
      denominacion,
      fase,
      infopublica_inicio,
      infopublica_fin,
      fecha_aprob,
      figura_codigo,
      tipo_figura,
      organo_tramitador,
      object_id,
      enlace,
      has_geometry,
      sigma_synced_at,
      updated_at
    FROM homes.proyecto
    WHERE expediente_grupo IS NOT NULL
       OR sigma_layer_kind IS NOT NULL
       OR bocm_municipio ILIKE 'madrid'
    ORDER BY COALESCE(sigma_synced_at, updated_at) DESC NULLS LAST
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 8000), 100), 8000)
  ) p;
$$;

REVOKE ALL ON FUNCTION homes.compute_list_proyectos_madrid(integer) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION homes.list_proyectos_madrid(p_limit integer DEFAULT 5000)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT jsonb_strip_nulls(payload)
  FROM homes.portal_snapshot
  WHERE name = 'list_proyectos_madrid'
    AND COALESCE(p_limit, 8000) > 0;
$$;
