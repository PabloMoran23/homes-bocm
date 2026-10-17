-- Deploy with Cursor paused. Existing research history is preserved.
BEGIN;
CREATE TABLE homes.proyecto_investigacion_lease (
  proyecto_id text PRIMARY KEY REFERENCES homes.proyecto(id) ON DELETE CASCADE,
  owner text NOT NULL CHECK (length(owner) > 0),
  token uuid NOT NULL,
  expires_at timestamptz NOT NULL,
  retry_after timestamptz,
  skip_reason text,
  investigacion_id bigint REFERENCES homes.proyecto_investigacion(id),
  payload_sha256 text
);
ALTER TABLE homes.proyecto_investigacion_lease ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.proyecto_investigacion_lease FROM PUBLIC, anon, authenticated;
GRANT ALL ON homes.proyecto_investigacion_lease TO service_role;

-- Every new research INSERT, including old clients, must hold a live lease.
-- Lock project first everywhere: claim, renew, release, save and this trigger.
CREATE FUNCTION homes.guard_proyecto_investigacion_lease() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, homes AS $$
DECLARE l homes.proyecto_investigacion_lease;
BEGIN
  PERFORM 1 FROM homes.proyecto WHERE id = NEW.proyecto_id FOR UPDATE;
  SELECT * INTO l FROM homes.proyecto_investigacion_lease
    WHERE proyecto_id = NEW.proyecto_id FOR UPDATE;
  IF l.proyecto_id IS NULL OR l.owner IS DISTINCT FROM current_setting('homes.research_owner', true)
     OR l.token::text IS DISTINCT FROM current_setting('homes.research_token', true)
     OR l.expires_at <= clock_timestamp() OR l.investigacion_id IS NOT NULL THEN
    RAISE EXCEPTION 'Live research lease required' USING ERRCODE = '55000';
  END IF;
  IF EXISTS (SELECT 1 FROM homes.proyecto_investigacion WHERE proyecto_id = NEW.proyecto_id) THEN
    RAISE EXCEPTION 'Project already researched' USING ERRCODE = '23505';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER proyecto_investigacion_require_lease BEFORE INSERT
  ON homes.proyecto_investigacion FOR EACH ROW EXECUTE FUNCTION homes.guard_proyecto_investigacion_lease();

-- Decode exactly one URL component, as decodeURIComponent does. Malformed paths
-- are unmapped, never guessed by title or partial identifier.
CREATE FUNCTION homes.research_route_id(path text) RETURNS text
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
CREATE VIEW homes.research_human_project_visits AS
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
