-- One active investigation history, retaining canonical subjects and relationships.
BEGIN;
LOCK TABLE homes.entrada_investigacion IN SHARE ROW EXCLUSIVE MODE;
ALTER TABLE homes.proyecto_investigacion
 ADD COLUMN request_id uuid UNIQUE,
 ADD COLUMN tipo_entrada text NOT NULL DEFAULT 'actuacion' CHECK(tipo_entrada IN ('actuacion','planeamiento','modificacion_normativa','documento','subasta','tramite','anuncio','pendiente')),
 ADD COLUMN asunto_id uuid REFERENCES homes.asunto(id),
 ADD COLUMN razon_pendiente text,
 ADD COLUMN fuentes jsonb NOT NULL DEFAULT '[]',
 ADD COLUMN busquedas_intentadas jsonb NOT NULL DEFAULT '[]',
 ADD COLUMN vinculos_pendientes jsonb NOT NULL DEFAULT '[]',
 ADD COLUMN payload jsonb,
 ADD COLUMN payload_sha256 text,
 ADD COLUMN source_hash text,
 ADD COLUMN execution_mode text NOT NULL DEFAULT 'legacy' CHECK(execution_mode IN ('legacy','leased','unleased_test')),
 ADD COLUMN entrada_legacy_id bigint UNIQUE;
ALTER TABLE homes.proyecto_investigacion DROP CONSTRAINT proyecto_investigacion_estado_check;
ALTER TABLE homes.proyecto_investigacion ADD CONSTRAINT proyecto_investigacion_estado_check
 CHECK(estado IN ('completa','parcial','pendiente_identificar'));
ALTER TABLE homes.proyecto_dato_extra ADD COLUMN raw_json jsonb;
ALTER TABLE homes.proyecto_hallazgo ADD COLUMN raw_json jsonb;

-- Use the existing lease table, independently of whether the legacy guard was deployed.
CREATE TABLE IF NOT EXISTS homes.proyecto_investigacion_lease (
 proyecto_id text PRIMARY KEY REFERENCES homes.proyecto(id) ON DELETE CASCADE,
 owner text NOT NULL,token uuid NOT NULL,expires_at timestamptz NOT NULL,
 retry_after timestamptz,skip_reason text,
 investigacion_id bigint REFERENCES homes.proyecto_investigacion(id),payload_sha256 text
);
ALTER TABLE homes.proyecto_investigacion_lease ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON homes.proyecto_investigacion_lease FROM PUBLIC,anon,authenticated;
GRANT ALL ON homes.proyecto_investigacion_lease TO service_role;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM homes.entrada_investigacion_lease e JOIN homes.proyecto_investigacion_lease p USING(proyecto_id)
   WHERE e.expires_at>clock_timestamp() AND p.expires_at>clock_timestamp() AND (e.owner,e.token) IS DISTINCT FROM (p.owner,p.token))
 THEN RAISE EXCEPTION 'Conflicting active research leases; retry when owners finish'; END IF;
END $$;
INSERT INTO homes.proyecto_investigacion_lease(proyecto_id,owner,token,expires_at)
 SELECT proyecto_id,owner,token,expires_at FROM homes.entrada_investigacion_lease
 ON CONFLICT(proyecto_id) DO UPDATE SET owner=EXCLUDED.owner,token=EXCLUDED.token,expires_at=EXCLUDED.expires_at
 WHERE homes.proyecto_investigacion_lease.expires_at<=clock_timestamp();

-- Upgrade an existing guard without installing one on deployments that never enabled it.
-- Modern investigations may append reviewed snapshots. Legacy behavior remains intact.
CREATE OR REPLACE FUNCTION homes.guard_proyecto_investigacion_lease() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,homes AS $$
DECLARE l homes.proyecto_investigacion_lease;
BEGIN
 IF NEW.request_id IS NOT NULL AND NEW.execution_mode='unleased_test'
    AND current_setting('homes.research_unleased_test',true)='on' THEN RETURN NEW; END IF;
 PERFORM 1 FROM homes.proyecto WHERE id=NEW.proyecto_id FOR UPDATE;
 SELECT * INTO l FROM homes.proyecto_investigacion_lease WHERE proyecto_id=NEW.proyecto_id FOR UPDATE;
 IF l.proyecto_id IS NULL OR l.owner IS DISTINCT FROM current_setting('homes.research_owner',true)
    OR l.token::text IS DISTINCT FROM current_setting('homes.research_token',true)
    OR l.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'Live research lease required'; END IF;
 IF NEW.request_id IS NULL AND (l.investigacion_id IS NOT NULL OR EXISTS(
    SELECT 1 FROM homes.proyecto_investigacion WHERE proyecto_id=NEW.proyecto_id))
 THEN RAISE EXCEPTION 'Project already researched'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION homes.research_safe_date(t text) RETURNS date LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
BEGIN
 IF t IS NULL OR t !~ '^\d{4}-\d{2}-\d{2}$' THEN RETURN NULL; END IF;
 RETURN t::date;
EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN RETURN NULL;
END $$;

-- Legacy experimental blocks are mapped conservatively; retain the exact input.
-- Context/search-only evidence is not promoted into public, verified web facts.
CREATE FUNCTION homes.research_dato_compatible(d jsonb,n integer) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT d || jsonb_build_object(
  'bloque',CASE
   WHEN d->>'bloque' IN ('situacion','programa','cifras','actores','prensa','cronologia') THEN d->>'bloque'
   WHEN d->>'bloque' IN ('contenido','modificaciones','condiciones') THEN 'programa'
   WHEN d->>'bloque' IN ('superficie') THEN 'cifras'
   WHEN d->>'bloque' IN ('beneficiario') THEN 'actores'
   WHEN d->>'bloque' IN ('publicacion','tramitacion') THEN 'cronologia'
   ELSE 'situacion' END,
  'confianza',CASE WHEN d->>'confianza' IN ('alta','media','baja') THEN d->>'confianza' ELSE 'baja' END,
  'fuente_tipo',CASE WHEN d->>'fuente_tipo' IN ('oficial','prensa','web') THEN d->>'fuente_tipo' ELSE 'web' END,
  'fuente_nombre',coalesce(d->>'fuente_nombre',d->>'fuente_tipo'),
  'publicable',coalesce(d->'publicable','true'::jsonb)='true'::jsonb
      AND d->>'fuente_tipo' IN ('oficial','prensa','web') AND coalesce(d->>'fuente_url','') ~ '^https?://',
  'orden',n,'raw_json',d)
$$;
CREATE FUNCTION homes.research_insert_children(inv bigint,project text,datos jsonb,hallazgos jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,homes AS $$
DECLARE item record; d jsonb;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM homes.proyecto_investigacion WHERE id=inv AND proyecto_id=project)
 THEN RAISE EXCEPTION 'Investigation/project mismatch'; END IF;
 FOR item IN SELECT value,ordinality FROM jsonb_array_elements(datos) WITH ORDINALITY LOOP
  d:=homes.research_dato_compatible(item.value,(item.ordinality-1)::integer);
  INSERT INTO homes.proyecto_dato_extra(investigacion_id,proyecto_id,bloque,clave,etiqueta,valor,
   valor_numero,unidad,confianza,fuente_tipo,fuente_nombre,fuente_url,fuente_fecha,extracto,destacado,publicable,orden,raw_json)
  VALUES(inv,project,d->>'bloque',d->>'clave',d->>'etiqueta',d->>'valor',
   CASE WHEN jsonb_typeof(d->'valor_numero')='number' THEN (d->>'valor_numero')::double precision ELSE NULL END,
   d->>'unidad',d->>'confianza',d->>'fuente_tipo',d->>'fuente_nombre',d->>'fuente_url',
   homes.research_safe_date(d->>'fuente_fecha'),d->>'extracto',coalesce(d->'destacado','false'::jsonb)='true'::jsonb,
   d->'publicable'='true'::jsonb,(d->>'orden')::integer,d->'raw_json');
 END LOOP;
 FOR item IN SELECT value,ordinality FROM jsonb_array_elements(hallazgos) WITH ORDINALITY LOOP
  d:=item.value;
  INSERT INTO homes.proyecto_hallazgo(investigacion_id,proyecto_id,titulo,cuerpo,fuente_nombre,fuente_url,
    fuente_fecha,nota,publicable,orden,raw_json)
  VALUES(inv,project,d->>'titulo',d->>'cuerpo',d->>'fuente_nombre',d->>'fuente_url',
    homes.research_safe_date(d->>'fuente_fecha'),d->>'nota',coalesce(d->'publicable','true'::jsonb)='true'::jsonb,
    (item.ordinality-1)::integer,d);
 END LOOP;
END $$;
REVOKE ALL ON FUNCTION homes.research_insert_children(bigint,text,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION homes.research_insert_children(bigint,text,jsonb,jsonb) TO service_role;

SELECT set_config('homes.research_unleased_test','on',true);
INSERT INTO homes.proyecto_investigacion(request_id,proyecto_id,tipo_entrada,asunto_id,estado,resumen,huecos,
 razon_pendiente,fuentes,busquedas_intentadas,vinculos_pendientes,payload,payload_sha256,source_hash,execution_mode,
 entrada_legacy_id,investigado_at)
 SELECT request_id,proyecto_id,tipo_entrada,asunto_id,estado,resumen,huecos,razon_pendiente,fuentes,
 busquedas_intentadas,vinculos_pendientes,payload,payload_sha256,source_hash,'unleased_test',id,created_at
 FROM homes.entrada_investigacion ORDER BY id;
DO $$ DECLARE r record; BEGIN
 FOR r IN SELECT p.id,p.proyecto_id,e.datos,e.hallazgos FROM homes.proyecto_investigacion p
   JOIN homes.entrada_investigacion e ON e.id=p.entrada_legacy_id LOOP
  PERFORM homes.research_insert_children(r.id,r.proyecto_id,r.datos,r.hallazgos);
 END LOOP;
 IF EXISTS(SELECT 1 FROM homes.entrada_investigacion e LEFT JOIN homes.proyecto_investigacion p ON p.entrada_legacy_id=e.id
   WHERE p.id IS NULL OR p.payload IS DISTINCT FROM e.payload OR p.request_id<>e.request_id
     OR (SELECT count(*) FROM homes.proyecto_dato_extra d WHERE d.investigacion_id=p.id)<>jsonb_array_length(e.datos)
     OR (SELECT count(*) FROM homes.proyecto_hallazgo h WHERE h.investigacion_id=p.id)<>jsonb_array_length(e.hallazgos))
 THEN RAISE EXCEPTION 'Regional migration verification failed'; END IF;
END $$;

ALTER TABLE homes.asunto_relacion DROP CONSTRAINT asunto_relacion_entrada_investigacion_id_fkey;
UPDATE homes.asunto_relacion r SET entrada_investigacion_id=p.id
 FROM homes.proyecto_investigacion p WHERE p.entrada_legacy_id=r.entrada_investigacion_id;
ALTER TABLE homes.asunto_relacion RENAME COLUMN entrada_investigacion_id TO investigacion_id;
ALTER TABLE homes.asunto_relacion ADD FOREIGN KEY(investigacion_id) REFERENCES homes.proyecto_investigacion(id);
ALTER TABLE homes.entrada_investigacion_actual DROP CONSTRAINT entrada_investigacion_actual_investigacion_id_fkey;
UPDATE homes.entrada_investigacion_actual c SET investigacion_id=p.id
 FROM homes.proyecto_investigacion p WHERE p.entrada_legacy_id=c.investigacion_id;
ALTER TABLE homes.entrada_investigacion_actual RENAME TO proyecto_investigacion_actual;
ALTER TABLE homes.proyecto_investigacion_actual ADD FOREIGN KEY(investigacion_id) REFERENCES homes.proyecto_investigacion(id);
INSERT INTO homes.proyecto_investigacion_actual(proyecto_id,investigacion_id)
 SELECT DISTINCT ON(proyecto_id) proyecto_id,id FROM homes.proyecto_investigacion
 ORDER BY proyecto_id,investigado_at DESC,id DESC ON CONFLICT DO NOTHING;
-- Start change tracking for old research at consolidation time; this is not evidence
-- that its historical investigation read this exact current version of the source.
UPDATE homes.proyecto_investigacion i SET source_hash=homes.research_entrada_source_hash(to_jsonb(p))
 FROM homes.proyecto p WHERE p.id=i.proyecto_id AND i.source_hash IS NULL;

DROP VIEW homes.entrada_investigacion_resumen;
CREATE VIEW homes.proyecto_investigacion_resumen AS
 SELECT p.id AS proyecto_id,i.id AS investigacion_id,i.tipo_entrada,i.estado,i.asunto_id,
 a.padre_id,a.titulo,i.resumen,i.razon_pendiente,i.investigado_at AS created_at,c.revision_solicitada,
 i.source_hash IS DISTINCT FROM homes.research_entrada_source_hash(to_jsonb(p)) AS fuente_cambiada
 FROM homes.proyecto_investigacion_actual c JOIN homes.proyecto p ON p.id=c.proyecto_id
 JOIN homes.proyecto_investigacion i ON i.id=c.investigacion_id LEFT JOIN homes.asunto a ON a.id=i.asunto_id;
REVOKE ALL ON homes.proyecto_investigacion_resumen FROM PUBLIC,anon,authenticated;
GRANT SELECT ON homes.proyecto_investigacion_resumen TO service_role;

CREATE FUNCTION homes.capture_proyecto_investigacion_actual() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,homes AS $$
BEGIN
 IF NEW.source_hash IS NULL THEN
  SELECT homes.research_entrada_source_hash(to_jsonb(p)) INTO NEW.source_hash FROM homes.proyecto p WHERE p.id=NEW.proyecto_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proyecto_investigacion_source_baseline BEFORE INSERT ON homes.proyecto_investigacion
 FOR EACH ROW EXECUTE FUNCTION homes.capture_proyecto_investigacion_actual();
CREATE FUNCTION homes.point_proyecto_investigacion_actual() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,homes AS $$
BEGIN
 INSERT INTO homes.proyecto_investigacion_actual(proyecto_id,investigacion_id) VALUES(NEW.proyecto_id,NEW.id)
 ON CONFLICT(proyecto_id) DO UPDATE SET investigacion_id=EXCLUDED.investigacion_id,revision_solicitada=false;
 RETURN NEW;
END $$;
CREATE TRIGGER proyecto_investigacion_current AFTER INSERT ON homes.proyecto_investigacion
 FOR EACH ROW EXECUTE FUNCTION homes.point_proyecto_investigacion_actual();

-- Retain a private immutable recovery copy, never used for selection or saving.
ALTER TABLE homes.entrada_investigacion RENAME TO entrada_investigacion_archivo_20261017;
REVOKE ALL ON homes.entrada_investigacion_archivo_20261017 FROM PUBLIC,anon,authenticated,service_role;
CREATE FUNCTION homes.reject_archived_research_write() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Archived research is read-only; use proyecto_investigacion'; END $$;
CREATE TRIGGER archived_research_readonly BEFORE INSERT OR UPDATE OR DELETE
 ON homes.entrada_investigacion_archivo_20261017 FOR EACH ROW EXECUTE FUNCTION homes.reject_archived_research_write();
DROP TABLE homes.entrada_investigacion_lease;

-- Do not expose internal payload/search metadata through inherited table-wide SELECT.
-- Existing browser consumers use the RPC; retain direct access to the original public columns.
REVOKE SELECT ON homes.proyecto_investigacion FROM anon,authenticated;
GRANT SELECT(id,proyecto_id,investigado_at,estado,resumen,huecos,tipo_entrada,asunto_id,razon_pendiente)
 ON homes.proyecto_investigacion TO anon,authenticated;
REVOKE SELECT ON homes.proyecto_dato_extra FROM anon,authenticated;
GRANT SELECT(id,investigacion_id,proyecto_id,bloque,clave,etiqueta,valor,valor_numero,unidad,confianza,
 fuente_tipo,fuente_nombre,fuente_url,fuente_fecha,extracto,destacado,publicable,orden)
 ON homes.proyecto_dato_extra TO anon,authenticated;
REVOKE SELECT ON homes.proyecto_hallazgo FROM anon,authenticated;
GRANT SELECT(id,investigacion_id,proyecto_id,titulo,cuerpo,fuente_nombre,fuente_url,fuente_fecha,nota,publicable,orden)
 ON homes.proyecto_hallazgo TO anon,authenticated;

-- Ficha web: última investigación publicable de un proyecto.

CREATE OR REPLACE FUNCTION homes.get_proyecto_info_extra(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  WITH match AS (
    SELECT p.id
    FROM homes.proyecto p
    WHERE p.id = trim(p_id)
       OR p.expediente_grupo = trim(p_id)
       OR p.bocm_primary_id = trim(p_id)
       OR p.id = 'bocm:' || trim(p_id)
    LIMIT 1
  ),
  inv AS (
    SELECT i.*
    FROM homes.proyecto_investigacion i
    JOIN match m ON m.id = i.proyecto_id
    ORDER BY i.investigado_at DESC, i.id DESC
    LIMIT 1
  )
  SELECT jsonb_build_object(
    'id', i.id,
    'proyectoId', i.proyecto_id,
    'investigadoAt', i.investigado_at,
    'estado', i.estado,
    'resumen', i.resumen,
    'huecos', i.huecos,
    'tipoEntrada', i.tipo_entrada,
    'asuntoId', i.asunto_id,
    'padreId', (SELECT a.padre_id FROM homes.asunto a WHERE a.id=i.asunto_id),
    'razonPendiente', i.razon_pendiente,
    'datos', COALESCE((
      SELECT jsonb_agg(
        jsonb_build_object(
          'bloque', d.bloque,
          'clave', d.clave,
          'etiqueta', d.etiqueta,
          'valor', d.valor,
          'valorNumero', d.valor_numero,
          'unidad', d.unidad,
          'confianza', d.confianza,
          'fuenteTipo', d.fuente_tipo,
          'fuenteNombre', d.fuente_nombre,
          'fuenteUrl', d.fuente_url,
          'fuenteFecha', d.fuente_fecha,
          'extracto', d.extracto,
          'destacado', d.destacado,
          'orden', d.orden
        )
        ORDER BY d.orden, d.id
      )
      FROM homes.proyecto_dato_extra d
      WHERE d.investigacion_id = i.id
        AND d.publicable
    ), '[]'::jsonb),
    'hallazgos', COALESCE((
      SELECT jsonb_agg(
        jsonb_build_object(
          'titulo', h.titulo,
          'cuerpo', h.cuerpo,
          'fuenteNombre', h.fuente_nombre,
          'fuenteUrl', h.fuente_url,
          'fuenteFecha', h.fuente_fecha,
          'orden', h.orden
        )
        ORDER BY h.orden, h.id
      )
      FROM homes.proyecto_hallazgo h
      WHERE h.investigacion_id = i.id
        AND h.publicable
    ), '[]'::jsonb)
  )
  FROM inv i;
$$;

CREATE OR REPLACE FUNCTION public.get_proyecto_info_extra(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  SELECT homes.get_proyecto_info_extra(p_id);
$$;

GRANT EXECUTE ON FUNCTION homes.get_proyecto_info_extra(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_proyecto_info_extra(text) TO anon, authenticated, service_role;

COMMIT;
