-- Additive regional research model. Does not change the legacy Cursor writer or activity eligibility.
BEGIN;
CREATE TABLE homes.asunto (
  id uuid PRIMARY KEY,
  clave_identidad text NOT NULL UNIQUE,
  tipo text NOT NULL CHECK(tipo IN ('actuacion','planeamiento','norma','subasta','expediente','documento','otro')),
  titulo text NOT NULL,
  municipio text,
  padre_id uuid REFERENCES homes.asunto(id),
  fuente_url text NOT NULL,
  extracto text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK(padre_id IS DISTINCT FROM id)
);
CREATE INDEX asunto_padre ON homes.asunto(padre_id);
CREATE TABLE homes.entrada_investigacion (
  id bigserial PRIMARY KEY,
  request_id uuid NOT NULL UNIQUE,
  proyecto_id text NOT NULL REFERENCES homes.proyecto(id),
  tipo_entrada text NOT NULL CHECK(tipo_entrada IN ('actuacion','planeamiento','modificacion_normativa','documento','subasta','tramite','anuncio','pendiente')),
  asunto_id uuid REFERENCES homes.asunto(id),
  estado text NOT NULL CHECK(estado IN ('completa','parcial','pendiente_identificar')),
  resumen text NOT NULL,
  huecos text,
  razon_pendiente text,
  fuentes jsonb NOT NULL,
  busquedas_intentadas jsonb NOT NULL,
  datos jsonb NOT NULL,
  hallazgos jsonb NOT NULL,
  vinculos_pendientes jsonb NOT NULL,
  payload jsonb NOT NULL,
  payload_sha256 text NOT NULL,
  source_hash text NOT NULL,
  execution_mode text NOT NULL CHECK(execution_mode IN ('leased','unleased_test')),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK(asunto_id IS NOT NULL OR (estado='pendiente_identificar' AND length(razon_pendiente)>0))
);
CREATE INDEX entrada_investigacion_proyecto ON homes.entrada_investigacion(proyecto_id,created_at DESC);
CREATE TABLE homes.asunto_relacion (
  origen_id uuid NOT NULL REFERENCES homes.asunto(id),
  destino_id uuid NOT NULL REFERENCES homes.asunto(id),
  tipo text NOT NULL CHECK(tipo IN ('pertenece_a','modifica','afecta_a','describe','vinculado_a')),
  certeza text NOT NULL CHECK(certeza IN ('confirmada','posible')),
  fuente_url text NOT NULL,
  extracto text NOT NULL,
  entrada_investigacion_id bigint NOT NULL REFERENCES homes.entrada_investigacion(id),
  PRIMARY KEY(origen_id,destino_id,tipo,entrada_investigacion_id),
  CHECK(origen_id<>destino_id),
  CHECK(tipo<>'pertenece_a' OR certeza='confirmada')
);
CREATE TABLE homes.entrada_investigacion_actual (
  proyecto_id text PRIMARY KEY REFERENCES homes.proyecto(id),
  investigacion_id bigint NOT NULL REFERENCES homes.entrada_investigacion(id),
  revision_solicitada boolean NOT NULL DEFAULT false
);
CREATE TABLE homes.entrada_investigacion_lease (
  proyecto_id text PRIMARY KEY REFERENCES homes.proyecto(id),
  owner text NOT NULL,
  token uuid NOT NULL,
  expires_at timestamptz NOT NULL
);
CREATE FUNCTION homes.research_entrada_source_hash(r jsonb) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$ SELECT md5((r-'updated_at')::text) $$;
-- Canonical parents are a forest. Serialize graph mutations so two concurrent
-- writers cannot each introduce half of a cycle. Possible links are separate.
CREATE FUNCTION homes.guard_asunto_parent() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,homes AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(17140000);
  IF NEW.padre_id IS NOT NULL AND EXISTS (
    WITH RECURSIVE ancestors(id,padre_id) AS (
      SELECT id,padre_id FROM homes.asunto WHERE id=NEW.padre_id
      UNION SELECT a.id,a.padre_id FROM homes.asunto a JOIN ancestors p ON a.id=p.padre_id
    ) SELECT 1 FROM ancestors WHERE id=NEW.id
  ) THEN RAISE EXCEPTION 'Cyclic asunto parent'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER asunto_parent_acyclic BEFORE INSERT OR UPDATE OF padre_id ON homes.asunto
  FOR EACH ROW EXECUTE FUNCTION homes.guard_asunto_parent();
CREATE VIEW homes.entrada_investigacion_resumen AS
 SELECT p.id AS proyecto_id,i.id AS investigacion_id,i.tipo_entrada,i.estado,i.asunto_id,
        a.padre_id,a.titulo,i.resumen,i.razon_pendiente,i.created_at,c.revision_solicitada,
        i.source_hash IS DISTINCT FROM homes.research_entrada_source_hash(to_jsonb(p)) AS fuente_cambiada
 FROM homes.entrada_investigacion_actual c JOIN homes.proyecto p ON p.id=c.proyecto_id
 JOIN homes.entrada_investigacion i ON i.id=c.investigacion_id LEFT JOIN homes.asunto a ON a.id=i.asunto_id;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['asunto','entrada_investigacion','asunto_relacion','entrada_investigacion_actual','entrada_investigacion_lease'] LOOP
  EXECUTE format('ALTER TABLE homes.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON homes.%I FROM PUBLIC,anon,authenticated',t);
  EXECUTE format('GRANT ALL ON homes.%I TO service_role',t);
 END LOOP;
END $$;
REVOKE ALL ON homes.entrada_investigacion_resumen FROM PUBLIC,anon,authenticated;
GRANT SELECT ON homes.entrada_investigacion_resumen TO service_role;
GRANT USAGE,SELECT ON SEQUENCE homes.entrada_investigacion_id_seq TO service_role;

-- Standalone human-session priority; independent of legacy research leases.
CREATE OR REPLACE FUNCTION homes.research_route_id(path text) RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
DECLARE component text; bytes bytea := ''::bytea; pos integer := 1; ch text;
BEGIN
  IF path !~ '^/proyecto/[^/]+/?$' THEN RETURN NULL; END IF;
  component := regexp_replace(substr(path,11), '/$', '');
  WHILE pos <= length(component) LOOP
    ch := substr(component,pos,1);
    IF ch = '%' THEN
      IF substr(component,pos+1,2) !~ '^[0-9A-Fa-f]{2}$' THEN RETURN NULL; END IF;
      bytes := bytes || decode(substr(component,pos+1,2),'hex'); pos := pos+3;
    ELSE
      bytes := bytes || convert_to(ch,'UTF8'); pos := pos+1;
    END IF;
  END LOOP;
  RETURN convert_from(bytes,'UTF8');
EXCEPTION WHEN OTHERS THEN RETURN NULL;
END $$;

-- Same "interesting" session definition as homes_analytics_report_filtered
-- (20261013190000), over ALL retained events, no new lookback or visit threshold.
-- Entire bot/admin sessions are excluded, even if the flag is on another page.
CREATE OR REPLACE VIEW homes.research_human_project_visits AS
WITH raw_pages AS (
  SELECT session_id,page_id,
    max(CASE WHEN event_name='page_engagement'
      THEN coalesce((props->>'active_seconds')::integer,0) ELSE 0 END) AS active_seconds
  FROM public.homes_analytics_events GROUP BY session_id,page_id
), human_sessions AS (
  SELECT e.session_id FROM public.homes_analytics_events e GROUP BY e.session_id
  HAVING NOT bool_or(coalesce(e.props->>'traffic_type','') IN ('bot','admin') OR e.path LIKE '/admin%')
    AND count(*) FILTER (WHERE event_name='page_view') BETWEEN 1 AND 100
    AND (count(*) FILTER (WHERE event_name='page_view') > 1
      OR count(*) FILTER (WHERE event_name IN ('document_click','outbound_click','boletin_buscar',
         'estadisticas_filtro','mapa_buscar','mapa_seleccionar','ficha_pestana')) > 0
      OR (SELECT sum(p.active_seconds) FROM raw_pages p WHERE p.session_id=e.session_id) >= 10)
), aliases AS (
  SELECT id AS proyecto_id,id AS route_id FROM homes.proyecto
  UNION SELECT id,bocm_primary_id FROM homes.proyecto WHERE bocm_primary_id IS NOT NULL
  UNION SELECT id,expediente_grupo FROM homes.proyecto WHERE expediente_grupo IS NOT NULL
  UNION SELECT id,substr(id,6) FROM homes.proyecto WHERE id LIKE 'bocm:%'
  UNION SELECT id,split_part(id,'/',1)||'-'||split_part(id,'/',2)||'-'||lpad(split_part(id,'/',3),5,'0')
    FROM homes.proyecto WHERE id ~ '^[0-9]+/[0-9]+/[0-9]+$'
  UNION SELECT id,replace(expediente_grupo,'/','-') FROM homes.proyecto
    WHERE expediente_grupo ~ '^[0-9]+/[0-9]+/[0-9]{5}$'
), unambiguous AS (
  SELECT route_id,min(proyecto_id) AS proyecto_id FROM aliases
  GROUP BY route_id HAVING count(DISTINCT proyecto_id)=1
), visits AS (
  SELECT e.session_id,homes.research_route_id(e.path) AS route_id
  FROM public.homes_analytics_events e JOIN human_sessions h USING (session_id)
  WHERE e.event_name IN ('page_view','ficha_proyecto_ver')
)
SELECT a.proyecto_id,count(DISTINCT v.session_id) AS human_sessions
FROM visits v JOIN unambiguous a USING (route_id) GROUP BY a.proyecto_id;
REVOKE ALL ON homes.research_human_project_visits FROM PUBLIC,anon,authenticated;
GRANT SELECT ON homes.research_human_project_visits TO service_role;
REVOKE ALL ON FUNCTION homes.research_route_id(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION homes.research_route_id(text) TO service_role;
COMMIT;
