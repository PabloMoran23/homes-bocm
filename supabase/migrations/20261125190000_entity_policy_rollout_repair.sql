-- A legacy SQL/JSON null means absent evidence. Preserve any other non-object
-- input intact under a reserved key while allowing classification metadata.
CREATE OR REPLACE FUNCTION homes.entity_classification_raw(value jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE jsonb_typeof(value)
    WHEN 'object' THEN value
    WHEN 'null' THEN '{}'::jsonb
    ELSE CASE WHEN value IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('_legacy_entity_raw',value) END
  END;
$$;

-- Se invalida solo evidencia de identidad/concesión, no derivaciones de GIS,
-- métricas, programas o metadatos de otras políticas.
CREATE OR REPLACE FUNCTION homes.entity_classification_input(r jsonb, t text) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_build_object('raw', homes.entity_classification_raw(r->CASE WHEN t='proyecto' THEN 'raw_features_json' ELSE 'raw_json' END) - '_entity_policy' - '_semantic_contract')
    || (SELECT COALESCE(jsonb_object_agg(key,value),'{}'::jsonb) FROM jsonb_each(r)
        WHERE key=ANY(CASE WHEN t='proyecto' THEN ARRAY['id','denominacion','enlace','visor_url','bocm_pdf_url','expediente_grupo','exp_numero_original','object_id','sigma_layer_kind','fuente','id_origen','municipio','municipio_slug','bocm_municipio','bocm_source_id']
        ELSE ARRAY['id','objeto','tipo_expediente','fecha_concesion','fuente','id_origen','licencia_key'] END));
$$;
CREATE OR REPLACE FUNCTION homes.enqueue_entity_classification() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE current_json jsonb; previous_json jsonb; raw_col text; old_raw jsonb; new_raw jsonb;
BEGIN
  raw_col := CASE WHEN TG_TABLE_NAME='proyecto' THEN 'raw_features_json' ELSE 'raw_json' END;
  new_raw := homes.entity_classification_raw(to_jsonb(NEW)->raw_col);
  IF TG_OP='UPDATE' THEN
    old_raw := homes.entity_classification_raw(to_jsonb(OLD)->raw_col);
    IF new_raw->'_entity_policy' IS NULL AND old_raw->'_entity_policy' IS NOT NULL THEN
      new_raw := new_raw || jsonb_build_object('_entity_policy',old_raw->'_entity_policy');
    ELSIF NOT COALESCE((new_raw->'_entity_policy') ? 'active',false)
      AND old_raw->'_entity_policy'->'active' IS NOT NULL THEN
      new_raw := jsonb_set(new_raw,'{_entity_policy,active}',old_raw->'_entity_policy'->'active');
    END IF;
  END IF;
  IF TG_TABLE_NAME='proyecto' THEN NEW.raw_features_json := new_raw;
  ELSE NEW.raw_json := new_raw; END IF;
  current_json := homes.entity_classification_input(to_jsonb(NEW), TG_TABLE_NAME);
  IF TG_OP='UPDATE' THEN
    previous_json := homes.entity_classification_input(to_jsonb(OLD), TG_TABLE_NAME);
    IF current_json IS NOT DISTINCT FROM previous_json THEN RETURN NEW; END IF;
  END IF;
  INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id)
  VALUES(TG_TABLE_NAME,NEW.id::text)
  ON CONFLICT(entity_table,entity_id) DO UPDATE SET queued_at=now(), attempts=0,last_error=NULL,reason='source_change';
  RETURN NEW;
END $$;
-- Las RPC instaladas conservan firma, permisos, orden y filtros actuales.
-- Se cambia solo la relación leída, no tablas de evidencia ni SQL de escritura.
-- La frontera de palabra evita tocar proyecto_documento/investigacion/etc.
CREATE OR REPLACE FUNCTION homes.activate_entity_policy() RETURNS boolean
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
  -- Corte único atómico: bloquea escritores, permite consultas del legado.
  LOCK TABLE homes.proyecto, homes.licencia IN SHARE MODE;
  IF EXISTS(SELECT 1 FROM homes.entity_reprocess_queue)
     OR EXISTS(SELECT 1 FROM homes.proyecto WHERE raw_features_json->'_entity_policy'->>'version' IS DISTINCT FROM target)
     OR EXISTS(SELECT 1 FROM homes.licencia WHERE raw_json->'_entity_policy'->>'version' IS DISTINCT FROM target) THEN
    RAISE EXCEPTION 'entity_policy_not_ready: histórico o cola pendientes; lecturas anteriores conservadas';
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
  -- Solo se publica el candidato listo cuando TODAS las filas están preparadas.
  UPDATE homes.proyecto SET raw_features_json=jsonb_set(raw_features_json,
    '{_entity_policy,active}', (raw_features_json->'_entity_policy')-'active')
    WHERE raw_features_json->'_entity_policy'->'active'->>'version' IS DISTINCT FROM target;
  UPDATE homes.licencia SET raw_json=jsonb_set(raw_json,
    '{_entity_policy,active}', (raw_json->'_entity_policy')-'active')
    WHERE raw_json->'_entity_policy'->'active'->>'version' IS DISTINCT FROM target;
  UPDATE homes.entity_policy_config SET version=target,active=true WHERE singleton;
  -- These calls see the activated policy in this transaction. A failure rolls
  -- back the activation and every payload together.
  IF refresh_portal THEN PERFORM homes.refresh_portal_snapshots(); END IF;
  IF refresh_cards THEN PERFORM homes.refresh_map_card_snapshots(); END IF;
  IF refresh_bocm THEN PERFORM homes.refresh_bocm_madrid_snapshot(); END IF;
  PERFORM pg_notify('pgrst','reload schema');
  RETURN true;
END $policy_rpc$;
-- Sin EXECUTE implícito: preparación y activación pertenecen al worker autorizado.
REVOKE ALL ON FUNCTION homes.activate_entity_policy() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION homes.activate_entity_policy() TO service_role;
