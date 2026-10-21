-- list_proyectos_bocm_madrid builds to_jsonb of each proyecto row and
-- times out under the anon 3s cap. Store one payload. This migration does
-- not scan the table; the cron at minute 48 fills it. That minute is after
-- the portal refresh at :37 and before the one at :52, and it does not
-- share a start with the map-card job at :15.

CREATE TABLE IF NOT EXISTS homes.portal_snapshot (
  name text PRIMARY KEY,
  payload jsonb NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE homes.portal_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.portal_snapshot FROM PUBLIC, anon, authenticated;
GRANT SELECT ON homes.portal_snapshot TO service_role;

-- Only the columns the Madrid BOCM explorer reads. Visor and geometry
-- blobs stay on the heap and are not decompressed.
CREATE OR REPLACE FUNCTION homes.compute_list_proyectos_bocm_madrid()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '45s'
AS $$
  SELECT jsonb_build_object(
    'generatedAt', COALESCE(MAX(p.updated_at), now())::text,
    'projects', COALESCE(
      jsonb_agg(
        jsonb_strip_nulls(
          jsonb_build_object(
            'id', p.id,
            'bocm_primary_id', p.bocm_primary_id,
            'bocm_source_id', p.bocm_source_id,
            'bocm_pub_date', p.bocm_pub_date,
            'bocm_art_num', p.bocm_art_num,
            'bocm_title', p.bocm_title,
            'bocm_pdf_url', p.bocm_pdf_url,
            'municipio', p.municipio,
            'bocm_municipio', p.bocm_municipio,
            'bocm_tipo_instrumento', p.bocm_tipo_instrumento,
            'bocm_nombre_sector', p.bocm_nombre_sector,
            'bocm_estado_tramitacion', p.bocm_estado_tramitacion,
            'bocm_fecha_acuerdo', p.bocm_fecha_acuerdo,
            'bocm_organo', p.bocm_organo,
            'bocm_promotor', p.bocm_promotor,
            'num_viviendas_max', p.num_viviendas_max,
            'sup_total_m2', p.sup_total_m2,
            'sup_edificable_m2', p.sup_edificable_m2,
            'tipo_vivienda', p.tipo_vivienda,
            'bocm_resumen', p.bocm_resumen,
            'bocm_municipio_provincia', p.bocm_municipio_provincia,
            'bocm_categorias_tematicas', p.bocm_categorias_tematicas,
            'bocm_economico_resumen', p.bocm_economico_resumen,
            'bocm_procedimiento_expediente', p.bocm_procedimiento_expediente,
            'bocm_procedimiento_tipo', p.bocm_procedimiento_tipo
          ) || jsonb_build_object(
            'importe_total_eur', p.importe_total_eur,
            'bocm_requiere_segunda_pasada', p.bocm_requiere_segunda_pasada,
            'bocm_chars_texto_total', p.bocm_chars_texto_total,
            'lat', p.lat,
            'lng', p.lng,
            'sector_key', p.sector_key,
            'sector_geo_key', p.sector_geo_key,
            'coord_source', p.coord_source,
            'bocm_es_relevante', p.bocm_es_relevante,
            'bocm_parse_error', p.bocm_parse_error,
            'bocm_sigma_match_type', p.bocm_sigma_match_type,
            'bocm_sigma_match_score', p.bocm_sigma_match_score,
            'expediente_grupo', p.expediente_grupo,
            'denominacion', p.denominacion
          ) || jsonb_build_object(
            'fase', p.fase,
            'enlace', p.enlace,
            'sigma_enlace_snapshot', p.sigma_enlace_snapshot,
            'sigma_layer_kind', p.sigma_layer_kind,
            'sigma_synced_at', p.sigma_synced_at,
            'figura_codigo', p.figura_codigo,
            'tipo_figura', p.tipo_figura,
            'organo_tramitador', p.organo_tramitador,
            'catalog_source', p.catalog_source,
            'object_id', p.object_id,
            'fecha_aprob', p.fecha_aprob,
            'infopublica_inicio', p.infopublica_inicio,
            'infopublica_fin', p.infopublica_fin,
            'has_geometry', p.has_geometry
          )
        )
        ORDER BY p.bocm_pub_date DESC NULLS LAST, p.bocm_primary_id
      ),
      '[]'::jsonb
    )
  )
  FROM (
    SELECT
      id, bocm_primary_id, bocm_source_id, bocm_pub_date, bocm_art_num,
      bocm_title, bocm_pdf_url, municipio, bocm_municipio, bocm_tipo_instrumento,
      bocm_nombre_sector, bocm_estado_tramitacion, bocm_fecha_acuerdo, bocm_organo,
      bocm_promotor, num_viviendas_max, sup_total_m2, sup_edificable_m2,
      tipo_vivienda, bocm_resumen, bocm_municipio_provincia, bocm_categorias_tematicas,
      bocm_economico_resumen, bocm_procedimiento_expediente, bocm_procedimiento_tipo,
      importe_total_eur, bocm_requiere_segunda_pasada, bocm_chars_texto_total,
      lat, lng, sector_key, sector_geo_key, coord_source, bocm_es_relevante,
      bocm_parse_error, bocm_sigma_match_type, bocm_sigma_match_score,
      expediente_grupo, denominacion, fase, enlace, sigma_enlace_snapshot,
      sigma_layer_kind, sigma_synced_at, figura_codigo, tipo_figura,
      organo_tramitador, catalog_source, object_id, fecha_aprob,
      infopublica_inicio, infopublica_fin, has_geometry, updated_at
    FROM homes.proyecto
    WHERE bocm_primary_id IS NOT NULL
      AND lower(trim(COALESCE(bocm_municipio, municipio, ''))) IN (
        'madrid',
        'madrid capital',
        'madrid, capital'
      )
  ) p;
$$;

CREATE OR REPLACE FUNCTION homes.refresh_bocm_madrid_snapshot()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = homes, pg_catalog
SET statement_timeout = '45s'
AS $$
BEGIN
  INSERT INTO homes.portal_snapshot (name, payload, refreshed_at)
  VALUES (
    'list_proyectos_bocm_madrid',
    homes.compute_list_proyectos_bocm_madrid(),
    clock_timestamp()
  )
  ON CONFLICT (name) DO UPDATE
    SET payload = EXCLUDED.payload,
        refreshed_at = EXCLUDED.refreshed_at;
END;
$$;

REVOKE ALL ON FUNCTION homes.compute_list_proyectos_bocm_madrid() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION homes.refresh_bocm_madrid_snapshot() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION homes.refresh_bocm_madrid_snapshot() TO service_role;

-- Missing row returns NULL. /api/dominio/projects-madrid then sends an
-- empty list and the page falls back to the checked-in projects JSON
-- until the first cron run.
CREATE OR REPLACE FUNCTION homes.list_proyectos_bocm_madrid()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, pg_catalog
AS $$
  SELECT payload FROM homes.portal_snapshot WHERE name = 'list_proyectos_bocm_madrid';
$$;

DO $cron$
BEGIN
  PERFORM cron.unschedule(jobid)
  FROM cron.job
  WHERE jobname = 'refresh-bocm-madrid-snapshot';
  PERFORM cron.schedule(
    'refresh-bocm-madrid-snapshot',
    '48 * * * *',
    'SELECT homes.refresh_bocm_madrid_snapshot()'
  );
EXCEPTION WHEN OTHERS THEN
  RAISE WARNING 'bocm madrid snapshot cron not scheduled: %', SQLERRM;
END
$cron$;
