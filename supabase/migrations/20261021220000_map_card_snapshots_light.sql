-- list_sigma_map_cards and web_summary time out on the request path.
-- This file only creates the snapshot readers and the cron. It does not
-- scan proyecto. The first cron run (minute 15, after the portal refresh
-- that starts at minute 7) fills the rows.
--
-- 20261021190000 is a no-op. Apply this file. It is safe if the portal
-- snapshot table already exists.

CREATE TABLE IF NOT EXISTS homes.portal_snapshot (
  name text PRIMARY KEY,
  payload jsonb NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE homes.portal_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.portal_snapshot FROM PUBLIC, anon, authenticated;
GRANT SELECT ON homes.portal_snapshot TO service_role;

-- jsonb_to_record detoasts visor_ficha once per row. The previous target
-- list called ->> four times and decompressed the same value each time.
CREATE OR REPLACE FUNCTION homes.compute_list_sigma_map_cards()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '45s'
AS $$
  WITH src AS MATERIALIZED (
    -- One output column, so the toasted value is decompressed once.
    SELECT
      expediente_grupo,
      denominacion,
      resumen_contenido,
      visor_ficha AS ficha
    FROM homes.proyecto
    WHERE expediente_grupo IS NOT NULL
      AND (
        visor_ficha IS NOT NULL
        OR NULLIF(resumen_contenido, '') IS NOT NULL
        OR NULLIF(denominacion, '') IS NOT NULL
      )
  )
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'byExpediente', COALESCE(
      jsonb_object_agg(p.expediente_grupo, p.card),
      '{}'::jsonb
    )
  )
  FROM (
    SELECT
      src.expediente_grupo,
      jsonb_strip_nulls(jsonb_build_object(
        'distrito', COALESCE(f.distrito, f."Distrito"),
        'ambitoLabel', COALESCE(
          NULLIF(f."ambitoOrdenacion", ''),
          NULLIF(f."descripcionAmbito", ''),
          NULLIF(src.denominacion, '')
        ),
        'resumen', COALESCE(
          NULLIF(src.resumen_contenido, ''),
          NULLIF(f."resumenContenido", ''),
          left(COALESCE(src.denominacion, ''), 280)
        )
      )) AS card
    FROM src
    LEFT JOIN LATERAL jsonb_to_record(
      CASE
        WHEN jsonb_typeof(src.ficha) = 'object' THEN src.ficha
        ELSE NULL
      END
    ) AS f(
      distrito text,
      "Distrito" text,
      "ambitoOrdenacion" text,
      "descripcionAmbito" text,
      "resumenContenido" text
    ) ON true
  ) p;
$$;

-- One narrow pass. The previous function scanned proyecto once per chart.
CREATE OR REPLACE FUNCTION homes.compute_web_summary()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '45s'
AS $$
  WITH base AS MATERIALIZED (
    SELECT
      COALESCE(NULLIF(municipio, ''), NULLIF(bocm_municipio, ''), '(sin municipio)') AS municipio,
      COALESCE(NULLIF(bocm_tipo_instrumento, ''), NULLIF(sigma_layer_kind, ''), '(otro)') AS tipo,
      CASE WHEN bocm_pub_date IS NULL THEN NULL ELSE extract(year FROM bocm_pub_date)::int END AS year,
      bocm_pub_date,
      COALESCE(NULLIF(fuente, ''), NULLIF(catalog_source, ''), 'desconocido') AS fuente,
      COALESCE(lat, centroid_lat) IS NOT NULL AS has_coords
    FROM homes.proyecto
  )
  SELECT jsonb_build_object(
    'generatedAt', now()::text,
    'total', (SELECT count(*)::int FROM base),
    'dateRange', jsonb_build_object(
      'min', (SELECT to_char(min(bocm_pub_date), 'YYYY-MM-DD') FROM base),
      'max', (SELECT to_char(max(bocm_pub_date), 'YYYY-MM-DD') FROM base)
    ),
    'byMunicipio', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT municipio AS n, count(*)::int AS c
        FROM base
        GROUP BY 1
        ORDER BY c DESC
        LIMIT 30
      ) t
    ), '[]'::jsonb),
    'byTipo', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT tipo AS n, count(*)::int AS c
        FROM base
        GROUP BY 1
        ORDER BY c DESC
        LIMIT 20
      ) t
    ), '[]'::jsonb),
    'byYear', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('year', t.y::text, 'count', t.c) ORDER BY t.y)
      FROM (
        SELECT year AS y, count(*)::int AS c
        FROM base
        WHERE year IS NOT NULL
        GROUP BY 1
      ) t
    ), '[]'::jsonb),
    'byTerritorio', jsonb_build_array(
      jsonb_build_object('name', 'comunidad-madrid', 'count', (SELECT count(*)::int FROM base))
    ),
    'bySource', COALESCE((
      SELECT jsonb_agg(jsonb_build_object('name', t.n, 'count', t.c) ORDER BY t.c DESC)
      FROM (
        SELECT fuente AS n, count(*)::int AS c
        FROM base
        GROUP BY 1
        ORDER BY c DESC
        LIMIT 15
      ) t
    ), '[]'::jsonb),
    'withCoords', (SELECT count(*)::int FROM base WHERE has_coords),
    'portal', jsonb_build_object('name', 'Homes', 'tagline', 'Urbanismo de Madrid')
  );
$$;

CREATE OR REPLACE FUNCTION homes.refresh_map_card_snapshots()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '45s'
AS $$
BEGIN
  INSERT INTO homes.portal_snapshot (name, payload, refreshed_at)
  VALUES
    ('list_sigma_map_cards', homes.compute_list_sigma_map_cards(), clock_timestamp()),
    ('web_summary', homes.compute_web_summary(), clock_timestamp())
  ON CONFLICT (name) DO UPDATE
    SET payload = EXCLUDED.payload,
        refreshed_at = EXCLUDED.refreshed_at;
END;
$$;

REVOKE ALL ON FUNCTION homes.compute_list_sigma_map_cards() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.compute_web_summary() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.refresh_map_card_snapshots() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION homes.refresh_map_card_snapshots() TO service_role;

-- Same signatures as the live functions. A missing row returns NULL until
-- the first cron run; the map route turns that into empty cards and
-- loadSummary falls back to the checked-in JSON.
CREATE OR REPLACE FUNCTION homes.list_sigma_map_cards()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload FROM homes.portal_snapshot WHERE name = 'list_sigma_map_cards';
$$;

CREATE OR REPLACE FUNCTION homes.web_summary()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload FROM homes.portal_snapshot WHERE name = 'web_summary';
$$;

-- Portal refresh currently starts at minutes 7, 22, 37 and 52 and runs
-- 20–28s. Move it to minutes 7 and 37 so it never shares a start with the
-- map-card job, and so the small instance is not refreshing four times an
-- hour. Dashboard freshness of 30 minutes matches the 10 minute page cache.
-- Map cards run hourly at minute 15, after the :07 portal job has finished.
DO $portal$
BEGIN
  PERFORM cron.unschedule(jobid)
  FROM cron.job
  WHERE jobname = 'refresh-portal-snapshots';
  PERFORM cron.schedule(
    'refresh-portal-snapshots',
    '7,37 * * * *',
    'SELECT homes.refresh_portal_snapshots()'
  );
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'portal snapshot cron not moved to every 30 minutes: %', SQLERRM;
END
$portal$;

DO $cards$
BEGIN
  PERFORM cron.unschedule(jobid)
  FROM cron.job
  WHERE jobname = 'refresh-map-card-snapshots';
  PERFORM cron.schedule(
    'refresh-map-card-snapshots',
    '15 * * * *',
    'SELECT homes.refresh_map_card_snapshots()'
  );
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'map card snapshot cron not scheduled: %', SQLERRM;
END
$cards$;
