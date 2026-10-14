-- Recursos originales permanecen en proyecto/licencia. Solo las vistas son actividad.
CREATE TABLE IF NOT EXISTS homes.entity_policy_config (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton), version text NOT NULL,
  target_version text NOT NULL, active boolean NOT NULL DEFAULT false
);
ALTER TABLE homes.entity_policy_config ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT false;
ALTER TABLE homes.entity_policy_config ADD COLUMN IF NOT EXISTS target_version text NOT NULL DEFAULT 'h01-v3-5c35bf508856';
INSERT INTO homes.entity_policy_config(singleton,version,target_version) VALUES (true, 'h01-v3-5c35bf508856', 'h01-v3-5c35bf508856')
ON CONFLICT(singleton) DO NOTHING;
CREATE TABLE IF NOT EXISTS homes.entity_reprocess_queue (
  entity_table text NOT NULL CHECK(entity_table IN ('proyecto','licencia')),
  entity_id text NOT NULL, queued_at timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0, last_error text, last_attempt_at timestamptz,
  reason text NOT NULL DEFAULT 'source_change',
  PRIMARY KEY(entity_table,entity_id)
);
ALTER TABLE homes.entity_reprocess_queue ADD COLUMN IF NOT EXISTS reason text NOT NULL DEFAULT 'source_change';
-- Se invalida solo evidencia de identidad/concesión, no derivaciones de GIS,
-- métricas, programas o metadatos de otras políticas.
CREATE OR REPLACE FUNCTION homes.entity_classification_input(r jsonb, t text) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_build_object('raw', COALESCE(r->CASE WHEN t='proyecto' THEN 'raw_features_json' ELSE 'raw_json' END,'{}'::jsonb) - '_entity_policy' - '_semantic_contract')
    || (SELECT COALESCE(jsonb_object_agg(key,value),'{}'::jsonb) FROM jsonb_each(r)
        WHERE key=ANY(CASE WHEN t='proyecto' THEN ARRAY['id','denominacion','enlace','visor_url','bocm_pdf_url','expediente_grupo','exp_numero_original','object_id','sigma_layer_kind','fuente','id_origen','municipio','municipio_slug','bocm_municipio','bocm_source_id']
        ELSE ARRAY['id','objeto','tipo_expediente','fecha_concesion','fuente','id_origen','licencia_key'] END));
$$;
CREATE OR REPLACE FUNCTION homes.enqueue_entity_classification() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE current_json jsonb; previous_json jsonb; raw_col text; old_raw jsonb; new_raw jsonb;
BEGIN
  raw_col := CASE WHEN TG_TABLE_NAME='proyecto' THEN 'raw_features_json' ELSE 'raw_json' END;
  IF TG_OP='UPDATE' THEN
    old_raw := COALESCE(to_jsonb(OLD)->raw_col,'{}'::jsonb);
    new_raw := COALESCE(to_jsonb(NEW)->raw_col,'{}'::jsonb);
    IF new_raw->'_entity_policy' IS NULL AND old_raw->'_entity_policy' IS NOT NULL THEN
      new_raw := new_raw || jsonb_build_object('_entity_policy',old_raw->'_entity_policy');
    ELSIF NOT COALESCE((new_raw->'_entity_policy') ? 'active',false)
      AND old_raw->'_entity_policy'->'active' IS NOT NULL THEN
      new_raw := jsonb_set(new_raw,'{_entity_policy,active}',old_raw->'_entity_policy'->'active');
    END IF;
    IF TG_TABLE_NAME='proyecto' THEN NEW.raw_features_json := new_raw;
    ELSE NEW.raw_json := new_raw; END IF;
  END IF;
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
DROP TRIGGER IF EXISTS entity_classification_changed ON homes.proyecto;
CREATE TRIGGER entity_classification_changed BEFORE INSERT OR UPDATE ON homes.proyecto
FOR EACH ROW EXECUTE FUNCTION homes.enqueue_entity_classification();
DROP TRIGGER IF EXISTS entity_classification_changed ON homes.licencia;
CREATE TRIGGER entity_classification_changed BEFORE INSERT OR UPDATE ON homes.licencia
FOR EACH ROW EXECUTE FUNCTION homes.enqueue_entity_classification();
INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id,reason)
SELECT 'proyecto',id::text,'policy_change' FROM homes.proyecto
WHERE raw_features_json->'_entity_policy'->>'version' IS DISTINCT FROM (SELECT target_version FROM homes.entity_policy_config WHERE singleton) ON CONFLICT DO NOTHING;
INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id,reason)
SELECT 'licencia',id::text,'policy_change' FROM homes.licencia
WHERE raw_json->'_entity_policy'->>'version' IS DISTINCT FROM (SELECT target_version FROM homes.entity_policy_config WHERE singleton) ON CONFLICT DO NOTHING;
-- Preparación sin corte: antes de activar se conserva explícitamente el legado.
-- Nunca se informa control activo durante esta fase.
CREATE OR REPLACE VIEW homes.proyecto_actividad AS
SELECT p.* FROM homes.proyecto p
WHERE NOT (SELECT active FROM homes.entity_policy_config WHERE singleton) OR (
 p.raw_features_json->'_entity_policy'->'active'->>'activity_eligible'='true'
 AND p.raw_features_json->'_entity_policy'->'active'->>'entity_type' IN ('expediente','actuacion')
 AND p.raw_features_json->'_entity_policy'->'active'->>'version'=(SELECT version FROM homes.entity_policy_config WHERE singleton)
 AND COALESCE(p.bocm_es_relevante,true)
 AND NOT EXISTS(SELECT 1 FROM homes.entity_reprocess_queue q WHERE q.entity_table='proyecto' AND q.entity_id=p.id::text AND q.reason='source_change'));
CREATE OR REPLACE VIEW homes.licencia_actividad AS
SELECT l.* FROM homes.licencia l
WHERE NOT (SELECT active FROM homes.entity_policy_config WHERE singleton) OR (
 l.raw_json->'_entity_policy'->'active'->>'activity_eligible'='true'
 AND l.raw_json->'_entity_policy'->'active'->>'entity_type' IN ('expediente','actuacion')
 AND l.raw_json->'_entity_policy'->'active'->>'grant_evidenced'='true'
 AND l.raw_json->'_entity_policy'->'active'->>'version'=(SELECT version FROM homes.entity_policy_config WHERE singleton)
 AND NOT EXISTS(SELECT 1 FROM homes.entity_reprocess_queue q WHERE q.entity_table='licencia' AND q.entity_id=l.id::text AND q.reason='source_change'));
-- Señal operativa persistente, también para escritor ajeno al mapeo común.
CREATE OR REPLACE VIEW homes.entity_policy_health AS
SELECT entity_table, count(*) AS pending, count(*) FILTER (WHERE attempts>0) AS failed,
 min(queued_at) AS oldest_pending FROM homes.entity_reprocess_queue GROUP BY entity_table;

-- Las RPC instaladas conservan firma, permisos, orden y filtros actuales.
-- Se cambia solo la relación leída, no tablas de evidencia ni SQL de escritura.
-- La frontera de palabra evita tocar proyecto_documento/investigacion/etc.
CREATE OR REPLACE FUNCTION homes.activate_entity_policy() RETURNS boolean
LANGUAGE plpgsql AS $policy_rpc$
DECLARE item record; definition text; target text;
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
    IF definition !~* '\m(FROM|JOIN)\s+homes\.(proyecto|licencia)(_actividad)?\M' THEN
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
  PERFORM pg_notify('pgrst','reload schema');
  RETURN true;
END $policy_rpc$;
-- Sin EXECUTE implícito: preparación y activación pertenecen al worker autorizado.
REVOKE ALL ON FUNCTION homes.activate_entity_policy() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION homes.activate_entity_policy() TO service_role;
CREATE OR REPLACE VIEW homes.entity_policy_rollout AS
SELECT active AS control_active, version AS active_version, target_version,
 (SELECT count(*) FROM homes.entity_reprocess_queue) AS pending,
 (SELECT count(*) FROM homes.entity_reprocess_queue WHERE attempts>0) AS failed
FROM homes.entity_policy_config WHERE singleton;
GRANT SELECT ON homes.proyecto_actividad, homes.licencia_actividad TO service_role;
GRANT ALL ON homes.entity_policy_config, homes.entity_reprocess_queue TO service_role;
GRANT SELECT ON homes.entity_policy_health, homes.entity_policy_rollout TO service_role;
NOTIFY pgrst, 'reload schema';
