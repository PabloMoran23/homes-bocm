"""Reconciliación transaccional del snapshot municipal de licencias de Madrid."""
from __future__ import annotations

import logging
import hashlib
import json
import csv
import gzip
import tempfile
from datetime import datetime, timezone
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from psycopg2.extras import RealDictCursor

from db.license_dates import parse_date

_LOG = logging.getLogger(__name__)

SOURCE_IDENTITY_FIELDS = {
    "anio_dataset", "ndp_edificio", "fecha_de_alta", "fecha_concesin",
    "tipo_de_expediente", "procedimiento", "tipo_via", "nombre_via", "nmero",
}


def source_fingerprint(row: dict) -> str:
    """Identidad completa contrastada con XLSX oficiales, nunca NDP aislado.

    Protección, interesados y otros detalles pueden haber sido corregidos por
    la fuente. El backup conserva íntegro el registro anterior.
    """
    normalized = {}
    for key, value in row.items():
        if key not in SOURCE_IDENTITY_FIELDS or value is None or value == "":
            continue
        text = str(value).strip()
        if not text:
            continue
        if key in {"fecha_de_alta", "fecha_concesin"}:
            parsed = parse_date(value, as_of=date(2100, 1, 1))
            text = parsed["value"] or text
        else:
            try:
                text = format(Decimal(text).normalize(), "f")
            except InvalidOperation:
                pass
        normalized[key] = text
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def legacy_evidence(raw_dir: Path) -> tuple[set[str], dict]:
    from sector_geometry.madrid_licencias_download import _rows_from_xlsx
    fingerprints = set()
    resources = {}
    for path in sorted(raw_dir.glob("licencias_urbanisticas_*.xlsx")):
        year = int(path.stem.rsplit("_", 1)[1])
        rows = _rows_from_xlsx(path, year)
        fingerprints.update(source_fingerprint(row) for row in rows)
        resources[str(year)] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows)}
        print(f"Evidencia histórica {year}: {len(rows)} filas", flush=True)
    if not fingerprints:
        raise ValueError("No hay XLSX originales para verificar la procedencia del legado")
    return fingerprints, resources


def prepare_row(record: dict) -> dict:
    from db.license_dates import license_temporal
    from db.license_territory import resolve_territory
    from municipio.entity_policy import annotate, POLICY_KEY
    row = {k: v for k, v in record.items() if k != POLICY_KEY}
    if resolve_territory(row)["municipioCode"] != "28079":
        raise ValueError("Registro sin procedencia verificable de Madrid")
    row.update(municipio_slug="madrid", fuente="madrid-opendata")
    dataset = row.get("source_dataset") or ""
    if dataset and not dataset.startswith("https://"):
        row["source_dataset"] = "https://datos.madrid.es/dataset/" + dataset
    temporal = license_temporal(row)
    row.update(fecha_alta=temporal["fields"]["fecha_alta"]["value"],
               fecha_concesion=temporal["fields"]["fecha_concesion"]["value"],
               anio_dataset=temporal["year"], temporal=temporal)
    row = annotate(row, kind="licencia")
    row[POLICY_KEY]["active"] = dict(row[POLICY_KEY])
    return row


def sync_snapshot(conn, records: list[dict], *, evidence: set[str] | None = None,
                  apply: bool = False, schema: str = "homes") -> dict:
    """Caller owns the transaction. A failed assertion rolls back the entire swap.

    Only official-source Madrid rows and legacy rows proved against the original
    XLSX are replaced. Every previous row is archived before the atomic swap.
    pg_temp is reserved for integration tests with disposable temporary tables.
    """
    from municipio.entity_policy import POLICY_VERSION
    if schema not in {"homes", "pg_temp"}:
        raise ValueError("Unsupported schema")
    table = f"{schema}.licencia"
    with conn.cursor() as cur:
        cur.execute("SELECT version,target_version FROM homes.entity_policy_config WHERE singleton")
        if cur.fetchone() != (POLICY_VERSION, POLICY_VERSION):
            raise RuntimeError("La versión de clasificación de la base no coincide")
    prepared = {}
    digest = hashlib.sha256()
    for record in records:
        row = prepare_row(record)
        key = str(row.get("licencia_key") or row.get("id") or "")
        if not key or key in prepared:
            raise ValueError("Claves de licencia ausentes o duplicadas en el snapshot")
        prepared[key] = row
        if len(prepared) % 50000 == 0:
            _LOG.info("Clasificadas %s licencias", len(prepared))
        digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str).encode())
    if not prepared:
        raise ValueError("No se puede publicar un snapshot vacío")
    sources = {r.get("source_dataset") for r in prepared.values()}
    if not all(any(code in (s or "") for s in sources) for code in ("640505", "133556")):
        raise ValueError("El snapshot debe incluir ambos CSV municipales completos")
    source_digest = digest.hexdigest()
    if apply:
        # Acquire before reading scope, so a concurrent writer cannot add Madrid
        # rows between the scope snapshot and the replacement.
        with conn.cursor() as cur:
            if schema == "homes":
                cur.execute("SELECT version,target_version FROM homes.entity_policy_config WHERE singleton FOR SHARE")
                if cur.fetchone() != (POLICY_VERSION, POLICY_VERSION):
                    raise RuntimeError("La clasificación cambió durante la preparación")
            cur.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")
            if schema == "homes":
                cur.execute("SELECT pg_advisory_xact_lock(85020261103)")
    scope, unknown = [], 0
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT id,licencia_key,municipio_slug,CASE WHEN municipio_slug IS NULL THEN raw_json END AS raw_json FROM {table} WHERE (municipio_slug='madrid' AND fuente='madrid-opendata') OR (municipio_slug IS NULL AND fuente IS NULL) ORDER BY id")
        for row in cur:
            if row["municipio_slug"] == "madrid" or (evidence and source_fingerprint(row["raw_json"] or {}) in evidence):
                scope.append(row)
            else:
                unknown += 1
    keys = set(prepared)
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.madrid_license_snapshot_runs",))
        if cur.fetchone()[0]:
            cur.execute(f"SELECT source_digest FROM {schema}.madrid_license_snapshot_runs ORDER BY applied_at DESC LIMIT 1")
            previous = cur.fetchone()
            if previous and previous[0] == source_digest and keys == {r["licencia_key"] for r in scope}:
                return {"status": "unchanged", "rows": len(keys), "source_digest": source_digest}
    _LOG.info("Snapshot: %s filas; anteriores: %s; legado no atribuido: %s", len(keys), len(scope), unknown)
    existing = {r["licencia_key"]: r for r in scope}
    by_original = {}
    for row in scope:
        raw = row["raw_json"] or {}
        if all(k in raw for k in ("ndp_edificio", "anio_dataset", "fecha_de_alta")):
            by_original.setdefault(source_fingerprint(raw), []).append(row)
    months = {}
    for row in prepared.values():
        month = row["temporal"]["month"]
        if month:
            months[month] = months.get(month, 0) + 1
    report = {"status": "planned", "rows": len(keys), "previous_rows": len(scope),
              "unproven_legacy_untouched": unknown, "source_digest": source_digest,
              "by_month_2026": {k: v for k, v in sorted(months.items()) if k.startswith("2026")},
              "quarantined": sum(bool(r["temporal"]["quarantine"]) for r in prepared.values())}
    if not apply:
        return report
    if len(keys) < .8 * len(scope):
        raise ValueError("El snapshot pierde más del 20% de registros; no se modifica la base")
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('statement_timeout')")
        previous_timeout = cur.fetchone()[0]
        cur.execute("SELECT set_config('statement_timeout','900000',true)")
        cur.execute("SELECT conname FROM pg_constraint WHERE contype='f' AND confrelid=%s::regclass", (table,))
        if cur.fetchall():
            raise RuntimeError("Hay referencias externas a licencias; se requiere migrar esos vínculos primero")
        cur.execute(f"CREATE TABLE IF NOT EXISTS {schema}.madrid_license_snapshot_runs (batch_id text PRIMARY KEY, source_digest text NOT NULL, row_count integer NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        cur.execute(f"CREATE TABLE IF NOT EXISTS {schema}.madrid_license_snapshot_backup (batch_id text NOT NULL, licencia_id bigint NOT NULL, row_data jsonb NOT NULL, PRIMARY KEY(batch_id,licencia_id))")
        cur.execute("CREATE TEMP TABLE madrid_license_scope(id bigint PRIMARY KEY) ON COMMIT DROP")
        with tempfile.TemporaryFile(mode="w+t") as stream:
            for row in scope:
                stream.write(str(row["id"]) + "\n")
            stream.seek(0)
            cur.copy_expert("COPY madrid_license_scope(id) FROM STDIN", stream)
        cur.execute("ANALYZE madrid_license_scope(id)")
        cur.execute(f"SELECT count(*) FROM {table} l JOIN madrid_license_scope s USING(id)")
        if cur.fetchone()[0] != len(scope):
            raise RuntimeError("La carga anterior cambió durante la preparación; repetir")
        batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        cur.execute(f"INSERT INTO {schema}.madrid_license_snapshot_backup SELECT %s,l.id,to_jsonb(l) FROM {table} l JOIN madrid_license_scope s USING(id)", (batch,))
        cur.execute(f"CREATE TEMP TABLE madrid_license_links ON COMMIT DROP AS SELECT id,inserted_at,proyecto_id,proyecto_match_method,proyecto_match_score,proyecto_sigma_layer_kind,proyecto_linked_at FROM {table} JOIN madrid_license_scope USING(id)")
        cur.execute("CREATE UNIQUE INDEX ON madrid_license_links(id)")
        cur.execute("ANALYZE madrid_license_links(id)")
        cur.execute("""CREATE TEMP TABLE madrid_license_stage (
          id bigint, licencia_key text PRIMARY KEY, ndp text NOT NULL, anio_dataset integer,
          fecha_alta text,fecha_concesion text,procedimiento text,tipo_expediente text,
          uso text,interesado text,objeto text,unidad text,lat double precision,lng double precision,
          direccion text,distrito text,barrio text,coord_source text,raw_json jsonb NOT NULL
        ) ON COMMIT DROP""")
        used = set()
        with tempfile.TemporaryFile(mode="w+t") as stream:
            writer = csv.writer(stream)
            for key, row in prepared.items():
                previous = existing.get(key)
                if previous is None:
                    matches = by_original.get(source_fingerprint(row.get("original") or {}), [])
                    previous = matches[0] if len(matches) == 1 else None
                ident = previous["id"] if previous and previous["id"] not in used else None
                if ident is not None:
                    used.add(ident)
                writer.writerow([ident, key, str(row["ndp_edificio"]), row.get("anio_dataset"),
                    row.get("fecha_alta"),row.get("fecha_concesion"),row.get("procedimiento"),
                    row.get("tipo_expediente"),row.get("uso"),row.get("interesado"),
                    row.get("objeto") or row.get("titulo"),row.get("unidad"),row.get("lat"),row.get("lng"),
                    row.get("direccion"),row.get("distrito"),row.get("barrio"),row.get("coord_source"),
                    json.dumps(row, ensure_ascii=False, default=str)])
            stream.seek(0)
            cur.copy_expert("COPY madrid_license_stage FROM STDIN WITH (FORMAT CSV)", stream)
        cur.execute(f"""WITH ids AS (SELECT licencia_key,row_number() OVER(ORDER BY licencia_key)+(SELECT coalesce(max(id),0) FROM {table}) AS ident FROM madrid_license_stage WHERE id IS NULL)
          UPDATE madrid_license_stage s SET id=ids.ident FROM ids WHERE ids.licencia_key=s.licencia_key""")
        cur.execute("CREATE UNIQUE INDEX ON madrid_license_stage(id)")
        cur.execute("ANALYZE madrid_license_stage(id,licencia_key,ndp)")
        cur.execute("ANALYZE madrid_license_scope(id)")
        outside_sql = f"""SELECT count(*),md5(string_agg(l.id::text||':'||md5(to_jsonb(l)::text),',' ORDER BY l.id)) FROM {table} l
          WHERE NOT EXISTS(SELECT 1 FROM madrid_license_scope x WHERE x.id=l.id)
            AND NOT EXISTS(SELECT 1 FROM madrid_license_stage x WHERE x.id=l.id)"""
        cur.execute(outside_sql)
        outside_before = cur.fetchone()
        cur.execute(f"""INSERT INTO {schema}.inmueble(ndp_edificio,direccion,distrito,barrio,lat,lng,coord_source,inserted_at,updated_at)
          SELECT DISTINCT ON(ndp) ndp,direccion,distrito,barrio,lat,lng,coord_source,now(),now()
          FROM madrid_license_stage ORDER BY ndp,(lat IS NOT NULL) DESC
          ON CONFLICT(ndp_edificio) DO UPDATE SET direccion=coalesce(excluded.direccion,{schema}.inmueble.direccion),
          distrito=coalesce(excluded.distrito,{schema}.inmueble.distrito),barrio=coalesce(excluded.barrio,{schema}.inmueble.barrio),
          lat=coalesce({schema}.inmueble.lat,excluded.lat),lng=coalesce({schema}.inmueble.lng,excluded.lng),updated_at=now()""")
        # These two derived effects are already computed for the entire batch.
        # The table lock excludes all writers. Trigger DDL is transactional: on
        # failure rollback restores it, and on success we restore before commit.
        cur.execute("SELECT tgname,tgenabled FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=ANY(%s)",
                    (table, ["entity_classification_changed", "licencia_territory_invalidation"]))
        paused = [(name, mode) for name, mode in cur.fetchall() if mode != "D"]
        modes = {"O": "ENABLE", "A": "ENABLE ALWAYS", "R": "ENABLE REPLICA"}
        for name, mode in paused:
            if mode not in modes:
                raise RuntimeError("Modo de trigger desconocido")
            cur.execute(f'ALTER TABLE {table} DISABLE TRIGGER "{name}"')
        _LOG.info("Copia y staging listos; sustituyendo el lote en la transacción")
        cur.execute(f"DELETE FROM {table} l USING madrid_license_scope s WHERE l.id=s.id")
        insert_sql = f"""INSERT INTO {table}(id,licencia_key,inmueble_id,anio_dataset,fecha_alta,fecha_concesion,
          procedimiento,tipo_expediente,uso,interesado,objeto,unidad,lat,lng,raw_json,municipio_slug,fuente,id_origen,
          inserted_at,updated_at,proyecto_id,proyecto_match_method,proyecto_match_score,proyecto_sigma_layer_kind,proyecto_linked_at)
          SELECT s.id,s.licencia_key,i.id,s.anio_dataset,s.fecha_alta,s.fecha_concesion,s.procedimiento,s.tipo_expediente,
          s.uso,s.interesado,s.objeto,s.unidad,coalesce(s.lat,i.lat),coalesce(s.lng,i.lng),s.raw_json,
          'madrid','madrid-opendata',s.licencia_key,coalesce(o.inserted_at,now()),now(),
          o.proyecto_id,o.proyecto_match_method,o.proyecto_match_score,o.proyecto_sigma_layer_kind,o.proyecto_linked_at
          FROM madrid_license_stage s JOIN {schema}.inmueble i ON i.ndp_edificio=s.ndp LEFT JOIN madrid_license_links o ON o.id=s.id
          WHERE s.id BETWEEN %s AND %s"""
        cur.execute("SELECT id FROM madrid_license_stage ORDER BY id")
        ordered_ids = [r[0] for r in cur.fetchall()]
        inserted = 0
        for offset in range(0, len(ordered_ids), 10000):
            batch_ids = ordered_ids[offset:offset + 10000]
            bounds = (batch_ids[0], batch_ids[-1])
            if offset == 0:
                cur.execute("EXPLAIN " + insert_sql, bounds)
                _LOG.info("Plan del primer lote: %s", "; ".join(r[0] for r in cur.fetchall()))
            cur.execute(insert_sql, bounds)
            inserted += cur.rowcount
            _LOG.info("Insertadas %s / %s licencias", inserted, len(keys))
        if inserted != len(keys):
            raise RuntimeError("Recuento insertado distinto del snapshot")
        for name, mode in paused:
            cur.execute(f'ALTER TABLE {table} {modes[mode]} TRIGGER "{name}"')
        if any(name == "licencia_territory_invalidation" for name, _ in paused):
            cur.execute(f"""INSERT INTO {schema}.license_territory_rebuild VALUES ('madrid',now(),'license_changed')
              ON CONFLICT(municipio_slug) DO UPDATE SET requested_at=excluded.requested_at,reason=excluded.reason""")
        cur.execute(f"""DELETE FROM {schema}.entity_reprocess_queue q USING
          (SELECT id::text AS entity_id FROM madrid_license_scope UNION SELECT id::text FROM madrid_license_stage) s
          WHERE q.entity_table='licencia' AND q.entity_id=s.entity_id""")
        cur.execute(outside_sql)
        if cur.fetchone() != outside_before:
            raise RuntimeError("Se ha modificado una licencia ajena al snapshot de Madrid")
        cur.execute(f"INSERT INTO {schema}.madrid_license_snapshot_runs(batch_id,source_digest,row_count,applied_at) VALUES(%s,%s,%s,clock_timestamp())", (batch,source_digest,len(keys)))
        cur.execute("SELECT set_config('statement_timeout',%s,true)", (previous_timeout,))
    return {**report, "status": "applied", "batch_id": batch, "outside_rows_unchanged": outside_before[0]}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    import argparse
    import psycopg2
    from db.ingest import pg_url
    from municipio.madrid_export import build_licencias
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    evidence = None
    if args.evidence:
        with gzip.open(args.evidence, "rt") as stream:
            evidence = set(json.load(stream)["fingerprints"])
    records = build_licencias(args.jsonl)
    print(f"Snapshot preparado: {len(records)} claves únicas", flush=True)
    with psycopg2.connect(pg_url(), connect_timeout=15, application_name="madrid-license-snapshot",
                         options="-c statement_timeout=300000 -c lock_timeout=30000") as conn:
        report = sync_snapshot(conn, records, evidence=evidence, apply=args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
