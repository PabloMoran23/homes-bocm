-- list_sigma_map_cards and web_summary scan homes.proyecto (visor_ficha is
-- toasted) and die under the anon 3s statement_timeout. Request paths read
-- one stored row. This does not replace homes.refresh_portal_snapshots(),
-- so it can be applied before or after the Madrid snapshot migration.
-- A missing row returns NULL; the app already treats that as empty cards
-- or the checked-in summary JSON.

CREATE TABLE IF NOT EXISTS homes.portal_snapshot (
  name text PRIMARY KEY,
  payload jsonb NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE homes.portal_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.portal_snapshot FROM PUBLIC, anon, authenticated;
GRANT SELECT ON homes.portal_snapshot TO service_role;

CREATE OR REPLACE FUNCTION homes.compute_list_sigma_map_cards()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '120s'
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

CREATE OR REPLACE FUNCTION homes.compute_web_summary()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '120s'
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

CREATE OR REPLACE FUNCTION homes.refresh_map_card_snapshots()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '180s'
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

-- Same signatures as before. CREATE OR REPLACE keeps the anon grants.
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

-- Fill once. A timeout here must not roll back the functions: the readers
-- return NULL until a later refresh, which is fast, instead of scanning.
DO $fill$
BEGIN
  PERFORM homes.refresh_map_card_snapshots();
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'map card snapshot fill skipped: %', SQLERRM;
END
$fill$;

-- Four times an hour, offset from the Madrid snapshot cron. If pg_cron
-- cannot be created, the migration warns and still succeeds. Schedule
-- SELECT homes.refresh_map_card_snapshots() from the Supabase cron UI.
DO $cron$
BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
  EXCEPTION WHEN OTHERS THEN
    CREATE EXTENSION IF NOT EXISTS pg_cron;
  END;
  PERFORM cron.schedule(
    'refresh-map-card-snapshots',
    '9,24,39,54 * * * *',
    'SELECT homes.refresh_map_card_snapshots()'
  );
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'map card snapshot cron not scheduled: %', SQLERRM;
END
$cron$;
