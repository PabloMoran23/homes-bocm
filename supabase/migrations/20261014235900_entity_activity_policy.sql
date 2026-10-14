-- Recursos originales permanecen en proyecto/licencia. Solo las vistas son actividad.
CREATE TABLE IF NOT EXISTS homes.entity_policy_config (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton), version text NOT NULL
);
INSERT INTO homes.entity_policy_config(singleton,version) VALUES (true, 'h01-v1-5c35bf508856')
ON CONFLICT(singleton) DO UPDATE SET version=EXCLUDED.version;
CREATE TABLE IF NOT EXISTS homes.entity_reprocess_queue (
  entity_table text NOT NULL CHECK(entity_table IN ('proyecto','licencia')),
  entity_id text NOT NULL, queued_at timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0, last_error text, last_attempt_at timestamptz,
  PRIMARY KEY(entity_table,entity_id)
);
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
DECLARE current_json jsonb; previous_json jsonb;
BEGIN
  current_json := homes.entity_classification_input(to_jsonb(NEW), TG_TABLE_NAME);
  IF TG_OP='UPDATE' THEN
    previous_json := homes.entity_classification_input(to_jsonb(OLD), TG_TABLE_NAME);
    IF current_json IS NOT DISTINCT FROM previous_json THEN RETURN NEW; END IF;
  END IF;
  INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id)
  VALUES(TG_TABLE_NAME,NEW.id::text)
  ON CONFLICT(entity_table,entity_id) DO UPDATE SET queued_at=now(), attempts=0,last_error=NULL;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS entity_classification_changed ON homes.proyecto;
CREATE TRIGGER entity_classification_changed AFTER INSERT OR UPDATE ON homes.proyecto
FOR EACH ROW EXECUTE FUNCTION homes.enqueue_entity_classification();
DROP TRIGGER IF EXISTS entity_classification_changed ON homes.licencia;
CREATE TRIGGER entity_classification_changed AFTER INSERT OR UPDATE ON homes.licencia
FOR EACH ROW EXECUTE FUNCTION homes.enqueue_entity_classification();
INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id)
SELECT 'proyecto',id::text FROM homes.proyecto ON CONFLICT DO NOTHING;
INSERT INTO homes.entity_reprocess_queue(entity_table,entity_id)
SELECT 'licencia',id::text FROM homes.licencia ON CONFLICT DO NOTHING;
CREATE OR REPLACE VIEW homes.proyecto_actividad AS
SELECT p.* FROM homes.proyecto p
WHERE p.raw_features_json->'_entity_policy'->>'activity_eligible'='true'
AND p.raw_features_json->'_entity_policy'->>'entity_type' IN ('expediente','actuacion')
AND p.raw_features_json->'_entity_policy'->>'version'=(SELECT version FROM homes.entity_policy_config WHERE singleton)
AND COALESCE(p.bocm_es_relevante,true)
AND NOT EXISTS(SELECT 1 FROM homes.entity_reprocess_queue q WHERE q.entity_table='proyecto' AND q.entity_id=p.id::text);
CREATE OR REPLACE VIEW homes.licencia_actividad AS
SELECT l.* FROM homes.licencia l
WHERE l.raw_json->'_entity_policy'->>'activity_eligible'='true'
AND l.raw_json->'_entity_policy'->>'entity_type' IN ('expediente','actuacion')
AND l.raw_json->'_entity_policy'->>'grant_evidenced'='true'
AND l.raw_json->'_entity_policy'->>'version'=(SELECT version FROM homes.entity_policy_config WHERE singleton)
AND NOT EXISTS(SELECT 1 FROM homes.entity_reprocess_queue q WHERE q.entity_table='licencia' AND q.entity_id=l.id::text);
-- Señal operativa persistente, también para escritor ajeno al mapeo común.
CREATE OR REPLACE VIEW homes.entity_policy_health AS
SELECT entity_table, count(*) AS pending, count(*) FILTER (WHERE attempts>0) AS failed,
 min(queued_at) AS oldest_pending FROM homes.entity_reprocess_queue GROUP BY entity_table;

-- Las RPC instaladas conservan firma, permisos, orden y filtros actuales.
-- Se cambia solo la relación leída, no tablas de evidencia ni SQL de escritura.
-- La frontera de palabra evita tocar proyecto_documento/investigacion/etc.
DO $policy_rpc$
DECLARE item record; definition text;
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
  FOR item IN
    SELECT p.oid, p.proname, p.proname || '(' || oidvectortypes(p.proargtypes) || ')' AS signature FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    JOIN pg_language l ON l.oid=p.prolang
    WHERE n.nspname='homes' AND p.prokind='f'
      AND p.proname IN (SELECT split_part(signature, '(', 1) FROM unnest(allowed) AS signature)
      AND p.provolatile IN ('s','i') AND l.lanname IN ('sql','plpgsql')

  LOOP
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
END $policy_rpc$;
GRANT SELECT ON homes.proyecto_actividad, homes.licencia_actividad TO service_role;
GRANT ALL ON homes.entity_policy_config, homes.entity_reprocess_queue TO service_role;
GRANT SELECT ON homes.entity_policy_health TO service_role;
NOTIFY pgrst, 'reload schema';
