-- The anon role's 3s statement_timeout kills madrid_dashboard_stats,
-- list_proyectos_investigados and list_proyectos_madrid on every call.
-- Precompute them into one row each. Request paths only read the row.
-- pg_cron refreshes the rows; a missed schedule leaves the previous payload.

CREATE TABLE IF NOT EXISTS homes.portal_snapshot (
  name text PRIMARY KEY,
  payload jsonb NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE homes.portal_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.portal_snapshot FROM PUBLIC, anon, authenticated;
GRANT SELECT ON homes.portal_snapshot TO service_role;

-- One heap scan of proyecto. The previous function scanned it once per chart.
CREATE OR REPLACE FUNCTION homes.compute_madrid_dashboard_stats()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '90s'
AS $$
DECLARE
  sig jsonb;
BEGIN
  -- One narrow pass. Chart filters match the previous function:
  -- totals and fase/figura/capa use the sigma population; categoría and
  -- tipo de obra count every proyecto that has those fields.
  WITH base AS MATERIALIZED (
    SELECT
      (expediente_grupo IS NOT NULL OR sigma_layer_kind IS NOT NULL) AS in_sigma,
      expediente_grupo,
      visor_fetched_at,
      has_geometry,
      COALESCE(pdfs_procesados, 0) AS pdfs,
      NULLIF(categoria_proyecto, '') AS categoria_proyecto,
      NULLIF(tipo_obra, '') AS tipo_obra,
      COALESCE(NULLIF(fase, ''), '(sin fase)') AS fase,
      COALESCE(NULLIF(figura_codigo, ''), '(sin figura)') AS figura,
      COALESCE(NULLIF(sigma_layer_kind, ''), '(sin capa)') AS layer,
      COALESCE(metric_num_viviendas_max, num_viviendas_max) AS viviendas,
      COALESCE(metric_sup_total_m2, sup_total_m2) AS sup_m2,
      CASE
        WHEN expediente_grupo IS NOT NULL AND split_part(expediente_grupo, '/', 2) ~ '^\d{4}$'
          THEN split_part(expediente_grupo, '/', 2)::int
        ELSE NULL
      END AS year
    FROM homes.proyecto
  )
  SELECT jsonb_build_object(
    'total', (SELECT count(*)::int FROM base WHERE in_sigma),
    'conVisorFicha', (SELECT count(*)::int FROM base WHERE in_sigma AND visor_fetched_at IS NOT NULL),
    'conTramitacion', (SELECT count(*)::int FROM base WHERE in_sigma AND visor_fetched_at IS NOT NULL),
    'conGeometry', (SELECT count(*)::int FROM base WHERE in_sigma AND has_geometry),
    'conMetricasPdf', (SELECT count(*)::int FROM base WHERE in_sigma AND pdfs > 0),
    'viviendasEnMetricas', (SELECT COALESCE(sum(viviendas) FILTER (WHERE viviendas IS NOT NULL), 0)::int FROM base WHERE in_sigma),
    'expedientesConViviendas', (SELECT count(*)::int FROM base WHERE in_sigma AND viviendas IS NOT NULL),
    'conClasificacion', (SELECT count(*)::int FROM base WHERE in_sigma AND categoria_proyecto IS NOT NULL),
    'seriesByYear', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('year', s.y, 'count', s.n) ORDER BY s.y)
      FROM (
        SELECT year AS y, count(*)::int AS n FROM base WHERE year IS NOT NULL GROUP BY 1
      ) s
    ), '[]'::jsonb),
    'byCategoriaProyecto', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT categoria_proyecto AS n, count(*)::int AS c FROM base
        WHERE categoria_proyecto IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT 20
      ) t
    ), '[]'::jsonb),
    'byTipoObra', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT tipo_obra AS n, count(*)::int AS c FROM base
        WHERE tipo_obra IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT 20
      ) t
    ), '[]'::jsonb),
    'byFase', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT fase AS n, count(*)::int AS c FROM base WHERE in_sigma GROUP BY 1 ORDER BY c DESC LIMIT 20
      ) t
    ), '[]'::jsonb),
    'byFiguraTipo', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT figura AS n, count(*)::int AS c FROM base WHERE in_sigma GROUP BY 1 ORDER BY c DESC LIMIT 20
      ) t
    ), '[]'::jsonb),
    'byLayer', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT layer AS n, count(*)::int AS c FROM base WHERE in_sigma GROUP BY 1 ORDER BY c DESC LIMIT 20
      ) t
    ), '[]'::jsonb),
    'topViviendas', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'expedienteGrupo', t.expediente_grupo,
        'viviendas', t.viviendas,
        'supM2', t.sup_m2
      ) ORDER BY t.viviendas DESC)
      FROM (
        SELECT expediente_grupo, viviendas::int AS viviendas, sup_m2
        FROM base
        WHERE expediente_grupo IS NOT NULL AND viviendas IS NOT NULL
        ORDER BY viviendas DESC NULLS LAST
        LIMIT 15
      ) t
    ), '[]'::jsonb)
  )
  INTO sig;

  RETURN jsonb_build_object(
    'generatedAt', now()::text,
    'licencias', jsonb_build_object(
      'generatedAt', now()::text,
      'totalRows', NULL,
      'withCoords', NULL,
      'years', '[]'::jsonb,
      'seriesByYear', '[]'::jsonb,
      'topUso', '[]'::jsonb,
      'topDistrito', '[]'::jsonb,
      'topProcedimiento', '[]'::jsonb,
      'topTipoExpediente', '[]'::jsonb
    ),
    'sigma', sig
  );
END;
$$;

-- Top 12 Madrid cards. Starts from the few publicable housing figures
-- instead of correlating every investigation.
CREATE INDEX IF NOT EXISTS idx_homes_dato_num_viviendas
  ON homes.proyecto_dato_extra (valor_numero DESC, investigacion_id)
  INCLUDE (proyecto_id)
  WHERE clave = 'num_viviendas' AND publicable AND valor_numero IS NOT NULL;

CREATE OR REPLACE FUNCTION homes.compute_list_proyectos_investigados()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '90s'
AS $$
DECLARE
  rec record;
  cards jsonb := '[]'::jsonb;
  n integer := 0;
  muni text;
  denom text;
  bocm_title text;
  estado text;
  resumen text;
  nombre text;
  superficie double precision;
  promotor text;
BEGIN
  FOR rec IN
    SELECT picked.viviendas, picked.investigacion_id, picked.proyecto_id
    FROM (
      SELECT DISTINCT ON (c.proyecto_id)
        d.valor_numero AS viviendas,
        d.investigacion_id,
        c.proyecto_id
      FROM homes.proyecto_dato_extra d
      JOIN homes.proyecto_investigacion_actual c ON c.investigacion_id = d.investigacion_id
      WHERE d.clave = 'num_viviendas'
        AND d.publicable
        AND d.valor_numero IS NOT NULL
      ORDER BY c.proyecto_id,
        CASE d.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END,
        d.orden, d.id
    ) picked
    ORDER BY picked.viviendas DESC, picked.investigacion_id
  LOOP
    SELECT p.municipio, p.denominacion, p.bocm_title
      INTO muni, denom, bocm_title
    FROM homes.proyecto p
    WHERE p.id = rec.proyecto_id;
    CONTINUE WHEN muni IS NULL OR lower(muni) <> 'madrid';
    denom := COALESCE(NULLIF(btrim(denom), ''), NULLIF(btrim(bocm_title), ''), rec.proyecto_id);

    SELECT i.estado, left(i.resumen, 480)
      INTO estado, resumen
    FROM homes.proyecto_investigacion i
    WHERE i.id = rec.investigacion_id;

    SELECT d.valor INTO nombre
    FROM homes.proyecto_dato_extra d
    WHERE d.investigacion_id = rec.investigacion_id
      AND d.clave = 'nombre_publico' AND d.publicable AND NULLIF(btrim(d.valor), '') IS NOT NULL
    ORDER BY d.orden, d.id
    LIMIT 1;

    SELECT d.valor_numero INTO superficie
    FROM homes.proyecto_dato_extra d
    WHERE d.investigacion_id = rec.investigacion_id
      AND d.clave = 'sup_total_m2' AND d.publicable AND d.valor_numero IS NOT NULL
    ORDER BY CASE d.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, d.orden, d.id
    LIMIT 1;

    SELECT NULLIF(btrim(d.valor), '') INTO promotor
    FROM homes.proyecto_dato_extra d
    WHERE d.investigacion_id = rec.investigacion_id
      AND d.clave = 'promotor' AND d.publicable
    ORDER BY d.orden, d.id
    LIMIT 1;

    cards := cards || jsonb_build_array(jsonb_build_object(
      'proyectoId', rec.proyecto_id,
      'municipio', muni,
      'denominacion', COALESCE(denom, rec.proyecto_id),
      'nombrePublico', nombre,
      'resumen', resumen,
      'estado', estado,
      'viviendas', rec.viviendas,
      'superficieM2', superficie,
      'promotor', promotor
    ));
    n := n + 1;
    EXIT WHEN n >= 12;
  END LOOP;
  RETURN cards;
END;
$$;

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
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 8000), 100), 8000)
  ) p;
$$;

CREATE OR REPLACE FUNCTION homes.refresh_portal_snapshots()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '90s'
AS $$
BEGIN
  INSERT INTO homes.portal_snapshot (name, payload, refreshed_at)
  VALUES
    ('madrid_dashboard_stats', homes.compute_madrid_dashboard_stats(), clock_timestamp()),
    ('list_proyectos_investigados', homes.compute_list_proyectos_investigados(), clock_timestamp()),
    ('list_proyectos_madrid', homes.compute_list_proyectos_madrid(8000), clock_timestamp())
  ON CONFLICT (name) DO UPDATE
    SET payload = EXCLUDED.payload,
        refreshed_at = EXCLUDED.refreshed_at;
END;
$$;

REVOKE ALL ON FUNCTION homes.compute_madrid_dashboard_stats() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.compute_list_proyectos_investigados() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.compute_list_proyectos_madrid(integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.refresh_portal_snapshots() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION homes.refresh_portal_snapshots() TO service_role;

-- Anon keeps the same signatures. A missing row returns NULL; the app
-- falls back to the checked-in JSON instead of running the slow query.
CREATE OR REPLACE FUNCTION homes.madrid_dashboard_stats()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload FROM homes.portal_snapshot WHERE name = 'madrid_dashboard_stats';
$$;

CREATE OR REPLACE FUNCTION homes.list_proyectos_investigados()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload FROM homes.portal_snapshot WHERE name = 'list_proyectos_investigados';
$$;

CREATE OR REPLACE FUNCTION homes.list_proyectos_madrid(p_limit integer DEFAULT 5000)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload
  FROM homes.portal_snapshot
  WHERE name = 'list_proyectos_madrid'
    AND COALESCE(p_limit, 8000) > 0;
$$;

-- Fill once so the first requests after this migration are not empty.
SELECT homes.refresh_portal_snapshots();

-- Refresh four times an hour. If pg_cron cannot be created here, the
-- warning is non-fatal: schedule the same SELECT from the Supabase cron UI,
-- or rely on the Vercel cron that calls the service-role route.
DO $cron$
BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
  EXCEPTION WHEN OTHERS THEN
    CREATE EXTENSION IF NOT EXISTS pg_cron;
  END;
  PERFORM cron.schedule(
    'refresh-portal-snapshots',
    '7,22,37,52 * * * *',
    'SELECT homes.refresh_portal_snapshots()'
  );
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'portal snapshot cron not scheduled: %', SQLERRM;
END
$cron$;
