-- Las RPC instaladas conservan firma, permisos, orden y filtros actuales.
-- Se cambia solo la relación leída, no tablas de evidencia ni SQL de escritura.
-- La frontera de palabra evita tocar proyecto_documento/investigacion/etc.
CREATE OR REPLACE FUNCTION homes.activate_entity_policy_prepared() RETURNS boolean
LANGUAGE plpgsql AS $policy_rpc$
DECLARE item record; definition text; target text; producer text; producer_info record;
  refresh_portal boolean := false; refresh_cards boolean := false; refresh_bocm boolean := false;
  allowed text[] := ARRAY[
    'get_proyecto_portal(text)', 'get_proyecto_info_extra(text)',
    'get_sigma_ficha(text)', 'get_sigma_clasificacion(text)',
    'get_ubicacion_ficha(text)', 'boletin_area(double precision, double precision, double precision, integer)',
    'list_proyectos_madrid(integer)', 'list_sigma_clasificacion()',
    'list_sigma_bocm_by_expediente()', 'list_proyectos_bocm_madrid()',
    'list_proyectos_investigados()', 'list_sigma_metrics()', 'list_sigma_map_cards()',
    'madrid_dashboard_stats()', 'web_summary()', 'map_cm_municipios()',
    'map_cm_portal()', 'map_sigma_geojson(integer, double precision, double precision, double precision, double precision, text, integer)',
    'map_ubicaciones_bbox(double precision, double precision, double precision, double precision, integer)',
    'map_cm_portal_municipio(text, date, date, double precision, double precision, double precision, double precision)',
    'map_cm_portal_view_100(text, date, date, double precision, double precision, double precision, double precision)'
  ];
BEGIN
  SELECT target_version INTO target FROM homes.entity_policy_config WHERE singleton FOR UPDATE;
  -- The bounded worker holds both table locks while it checks and promotes
  -- each ID range. The final cut completes that same transaction.
  IF (SELECT count(DISTINCT relation) FROM pg_locks
      WHERE locktype='relation' AND pid=pg_backend_pid() AND granted
        AND mode='ShareRowExclusiveLock'
        AND relation IN ('homes.proyecto'::regclass, 'homes.licencia'::regclass)) <> 2 THEN
    RAISE EXCEPTION 'entity_policy_not_ready: prepared activation requires both table locks';
  END IF;
  IF EXISTS (SELECT 1 FROM homes.entity_reprocess_queue) THEN
    RAISE EXCEPTION 'entity_policy_not_ready: cola pendiente; lecturas anteriores conservadas';
  END IF;
  FOR item IN
    SELECT p.oid, p.proname, p.provolatile, l.lanname, p.proname || '(' || oidvectortypes(p.proargtypes) || ')' AS signature FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    JOIN pg_language l ON l.oid=p.prolang
    WHERE n.nspname='homes' AND p.prokind='f'
      AND p.proname IN (SELECT split_part(signature, '(', 1) FROM unnest(allowed) AS signature)

  LOOP
    IF item.provolatile NOT IN ('s','i') OR item.lanname NOT IN ('sql','plpgsql') THEN
      RAISE EXCEPTION 'Contrato RPC inesperado para política H01: %', item.signature;
    END IF;
    IF NOT item.signature=ANY(allowed) THEN
      RAISE EXCEPTION 'Firma RPC inesperada para política H01: %', item.signature;
    END IF;
    definition := pg_get_functiondef(item.oid);
    producer := CASE item.signature
      WHEN 'madrid_dashboard_stats()' THEN 'compute_madrid_dashboard_stats()'
      WHEN 'list_proyectos_investigados()' THEN 'compute_list_proyectos_investigados()'
      WHEN 'list_proyectos_madrid(integer)' THEN 'compute_list_proyectos_madrid(integer)'
      WHEN 'list_sigma_map_cards()' THEN 'compute_list_sigma_map_cards()'
      WHEN 'web_summary()' THEN 'compute_web_summary()'
      WHEN 'list_proyectos_bocm_madrid()' THEN 'compute_list_proyectos_bocm_madrid()'
    END;
    IF producer IS NOT NULL
       AND definition ~* '\mFROM\s+homes\.portal_snapshot\M'
       AND position(quote_literal(item.proname) IN definition) > 0 THEN
      -- Preserve the public cached RPC and classify its exact snapshot producer.
      SELECT p.proname, l.lanname, pg_get_functiondef(p.oid) AS definition
      INTO producer_info FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang
      WHERE p.oid=to_regprocedure('homes.' || producer) AND p.prokind='f';
      IF NOT FOUND OR producer_info.lanname NOT IN ('sql','plpgsql') OR
         producer_info.definition !~* '\m(FROM|JOIN)\s+homes\.(proyecto|licencia)(_actividad)?\M' THEN
        RAISE EXCEPTION 'Productor de snapshot inesperado para política H01: %', producer;
      END IF;
      definition := producer_info.definition;
      refresh_portal := refresh_portal OR item.proname IN (
        'madrid_dashboard_stats','list_proyectos_investigados','list_proyectos_madrid');
      refresh_cards := refresh_cards OR item.proname IN ('list_sigma_map_cards','web_summary');
      refresh_bocm := refresh_bocm OR item.proname='list_proyectos_bocm_madrid';
    ELSIF definition !~* '\m(FROM|JOIN)\s+homes\.(proyecto|licencia)(_actividad)?\M' THEN
      RAISE EXCEPTION 'Lectura RPC inesperada para política H01: %', item.signature;
    END IF;
    definition := regexp_replace(definition,
      '\m(FROM|JOIN)\s+homes\.(proyecto|licencia)\M', '\1 homes.\2_actividad', 'gi');
    -- La vista tiene un tipo compuesto propio; el helper espera el original.
    definition := replace(definition, 'homes._proyecto_map_portal_row(p)',
      'homes._proyecto_map_portal_row(ROW(p.*)::homes.proyecto)');
    IF item.proname='list_proyectos_investigados' THEN
      definition := replace(definition, 'LEFT JOIN homes.proyecto_actividad', 'JOIN homes.proyecto_actividad');
    END IF;
    EXECUTE definition;
  END LOOP;
  UPDATE homes.entity_policy_config SET version=target,active=true WHERE singleton;
  -- These calls see the activated policy in this transaction. A failure rolls
  -- back the activation and every payload together.
  IF refresh_portal THEN PERFORM homes.refresh_portal_snapshots(); END IF;
  IF refresh_cards THEN PERFORM homes.refresh_map_card_snapshots(); END IF;
  IF refresh_bocm THEN PERFORM homes.refresh_bocm_madrid_snapshot(); END IF;
  PERFORM pg_notify('pgrst','reload schema');
  RETURN true;
END $policy_rpc$;
-- The maintenance workflow uses the PostgreSQL schema owner. Public API roles
-- keep the existing checked no-argument entry point and cannot use this one.
REVOKE ALL ON FUNCTION homes.activate_entity_policy_prepared() FROM PUBLIC, anon, authenticated, service_role;
