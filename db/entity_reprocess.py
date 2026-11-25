#!/usr/bin/env python3
"""Cola única para altas, cambios e histórico de clasificación H01.

Ejecutar tras migraciones/sync y antes de publicar. No accede a modelos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from municipio.entity_policy import POLICY_KEY, POLICY_VERSION, annotate, original
from psycopg2.extras import Json, RealDictCursor, execute_values

TABLES = {"proyecto": ("raw_features_json", "id"), "licencia": ("raw_json", "id")}


def ensure_schema(conn) -> None:
    """Code-first compatible: bootstrap idempotente ANTES de bloquear filas."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regprocedure('homes.activate_entity_policy()')")
        if cur.fetchone()[0] is not None:
            return
        cur.execute("SELECT pg_advisory_xact_lock(85020261014)")
        cur.execute("SELECT to_regprocedure('homes.activate_entity_policy()')")
        if cur.fetchone()[0] is None:
            cur.execute((ROOT / "supabase/migrations/20261014235900_entity_activity_policy.sql").read_text())
            print("entity_policy_preparing: bootstrap realizado; control_active=false hasta replay y activación", flush=True)


def require_policy_active(cur) -> None:
    """Un export nuevo no puede publicar legado fingiendo tener control activo."""
    cur.execute("SELECT to_regclass('homes.entity_policy_config')")
    row = cur.fetchone()
    if (next(iter(row.values())) if isinstance(row, dict) else row[0]) is None:
        raise RuntimeError("entity_policy_not_ready: ejecutar db/entity_reprocess.py antes de exportar")
    cur.execute("SELECT active,version,target_version FROM homes.entity_policy_config WHERE singleton")
    row = cur.fetchone()
    active, version, target = tuple(row.values()) if isinstance(row, dict) else row
    if not active:
        raise RuntimeError("entity_policy_preparing: control_active=false; ejecutar db/entity_reprocess.py antes de exportar")
    if version != POLICY_VERSION or target != version:
        raise RuntimeError("entity_policy_preparing: versión activa anterior; ejecutar db/entity_reprocess.py antes de exportar")


def activate_policy(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT homes.activate_entity_policy()")


def source_record(row: dict, table: str) -> dict:
    raw_col, _ = TABLES[table]
    raw = original(row.get(raw_col) or {})
    # Las columnas son evidencia auxiliar; el JSON original tiene prioridad.
    fields = ("denominacion", "enlace", "visor_url", "bocm_pdf_url", "expediente_grupo",
              "exp_numero_original", "object_id", "sigma_layer_kind", "fuente", "id_origen",
              "municipio", "municipio_slug", "bocm_municipio", "bocm_source_id") if table == "proyecto" else (
                  "objeto", "tipo_expediente", "fecha_concesion", "fuente", "id_origen", "licencia_key")
    for field in fields:
        if field not in raw and row.get(field) is not None:
            raw[field] = row[field]
    # Fecha concesión es un derivado antiguo: un mero `fecha` no prueba concesión.
    if table == "licencia" and "fecha" in raw and "fecha_concesion" not in (row.get(raw_col) or {}):
        raw.pop("fecha_concesion", None)
    return raw


def enqueue_stale(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE homes.entity_policy_config SET target_version=%s WHERE singleton AND target_version IS DISTINCT FROM %s",
                    (POLICY_VERSION, POLICY_VERSION))
        for table, (raw_col, _) in TABLES.items():
            cur.execute(f"""INSERT INTO homes.entity_reprocess_queue(entity_table, entity_id, reason)
                SELECT %s, id::text, 'policy_change' FROM homes.{table}
                WHERE {raw_col}->%s->>'version' IS DISTINCT FROM %s
                ON CONFLICT (entity_table, entity_id) DO NOTHING""", (table, POLICY_KEY, POLICY_VERSION))


def _metadata(row: dict, table: str, version: str, reason: str) -> dict:
    raw_col, _ = TABLES[table]
    derived = annotate(source_record(row, table), kind=table)
    metadata = {k: v for k, v in derived[POLICY_KEY].items() if k != "active"}
    previous = (row.get(raw_col) or {}).get(POLICY_KEY) or {}
    active = None
    if metadata["version"] == version:
        active = dict(metadata)
    elif reason == "policy_change" and isinstance(previous.get("active"), dict):
        # A prepared policy version keeps the active classification until rollout.
        active = previous["active"]
    return {**metadata, "active": active}


def classify_written(conn, table: str, ids: list[str]) -> None:
    """Publish classifications while the caller owns the entity write locks."""
    raw_col, id_col = TABLES[table]
    entity_ids = [int(key) for key in ids] if table == "licencia" else ids
    id_type = "bigint" if table == "licencia" else "text"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT version FROM homes.entity_policy_config WHERE singleton")
        version = cur.fetchone()["version"]
        cur.execute(f"""SELECT entity.*, q.reason AS queue_reason FROM homes.{table} entity
            JOIN homes.entity_reprocess_queue q ON q.entity_table=%s AND q.entity_id=entity.{id_col}::text
            WHERE q.entity_id=ANY(%s) AND entity.{id_col}=ANY(%s::{id_type}[])
            FOR UPDATE OF q""", (table, ids, entity_ids))
        updates = [
            (row[id_col], Json(_metadata(row, table, version, row["queue_reason"])))
            for row in cur
        ]
        if updates:
            execute_values(cur, f"""UPDATE homes.{table} entity SET {raw_col} =
                jsonb_set(coalesce(entity.{raw_col}, '{{}}'::jsonb), '{{_entity_policy}}', v.metadata)
                FROM (VALUES %s) AS v(id, metadata) WHERE entity.{id_col}=v.id""",
                updates, template=f"(%s::{id_type},%s::jsonb)", page_size=500)
            cur.execute("""DELETE FROM homes.entity_reprocess_queue
                WHERE entity_table=%s AND entity_id=ANY(%s)""", (table, [str(key) for key, _ in updates]))


def classify_written_projects(conn, ids: list[str]) -> None:
    for offset in range(0, len(ids), 500):
        classify_written(conn, "proyecto", ids[offset:offset + 500])


def reprocess_queue(conn, *, table: str | None = None, ids: list[str] | None = None, batch_size: int = 500) -> dict:
    """Bloquea fila+cola; fallo deja evidencia y pendiente para el siguiente intento."""
    stats = {"processed": 0, "failed": 0, "unknown": 0}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        filters, params = [], []
        if table:
            filters.append("entity_table=%s")
            params.append(table)
        if ids is not None:
            filters.append("entity_id=ANY(%s)")
            params.append([str(i) for i in ids])
        where = " AND ".join(filters) or "TRUE"
        cur.execute(f"SELECT * FROM homes.entity_reprocess_queue WHERE {where} ORDER BY queued_at LIMIT %s",
                    (*params, batch_size))
        pending = list(cur.fetchall())
        cur.execute("SELECT version, active FROM homes.entity_policy_config WHERE singleton")
        config = cur.fetchone()
        for item in pending:
            entity_table, entity_id = item["entity_table"], item["entity_id"]
            raw_col, _ = TABLES[entity_table]
            cur.execute("SAVEPOINT entity_classification")
            try:
                # Mismo orden que el escritor: primero entidad, después cola.
                # Así no hay inversión de locks entre trigger y worker.
                cur.execute(f"SELECT * FROM homes.{entity_table} WHERE id=%s FOR UPDATE SKIP LOCKED", (entity_id,))
                row = cur.fetchone()
                if row is None:
                    cur.execute(f"SELECT 1 FROM homes.{entity_table} WHERE id=%s", (entity_id,))
                    if cur.fetchone():
                        continue  # Otro worker/escritor posee la entidad.
                cur.execute("SELECT 1 FROM homes.entity_reprocess_queue WHERE entity_table=%s AND entity_id=%s FOR UPDATE SKIP LOCKED", (entity_table, entity_id))
                if cur.fetchone() is None:
                    continue
                if row:
                    metadata = _metadata(row, entity_table, config["version"], item["reason"])
                    # No reemplazar el original por la proyección con columnas auxiliares.
                    stored = {**(row.get(raw_col) or {}), POLICY_KEY: metadata}
                    cur.execute(f"UPDATE homes.{entity_table} SET {raw_col}=%s WHERE id=%s", (Json(stored), entity_id))
                    stats["unknown"] += metadata["entity_type"] == "pendiente"
                cur.execute("DELETE FROM homes.entity_reprocess_queue WHERE entity_table=%s AND entity_id=%s", (entity_table, entity_id))
                stats["processed"] += 1
            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT entity_classification")
                cur.execute("""UPDATE homes.entity_reprocess_queue SET attempts=attempts+1,
                    last_error=%s, last_attempt_at=now() WHERE entity_table=%s AND entity_id=%s""",
                            (str(exc)[:1000], entity_table, entity_id))
                stats["failed"] += 1
            finally:
                cur.execute("RELEASE SAVEPOINT entity_classification")
    return stats


def main() -> int:
    from ingest import connect
    total = {"processed": 0, "failed": 0, "unknown": 0}
    with connect() as conn:
        ensure_schema(conn)
        enqueue_stale(conn)
        conn.commit()
        while True:
            batch = reprocess_queue(conn)
            conn.commit()
            for key in total:
                total[key] += batch[key]
            if batch["failed"] or batch["processed"] < 500:
                break
        with conn.cursor() as cur:
            cur.execute("SELECT entity_table, count(*), count(*) FILTER (WHERE attempts>0) FROM homes.entity_reprocess_queue GROUP BY entity_table")
            backlog = cur.fetchall()
        if not total["failed"] and not backlog:
            try:
                activate_policy(conn)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print(json.dumps({**total, "status": "activation_failed", "error": str(exc)}))
                return 1
        with conn.cursor() as cur:
            cur.execute("SELECT control_active,active_version,target_version FROM homes.entity_policy_rollout")
            active, active_version, target_version = cur.fetchone()
        print(json.dumps({**total, "version": POLICY_VERSION, "backlog": backlog,
                          "control_active": active, "active_version": active_version, "target_version": target_version}))
    return 1 if total["failed"] or backlog or not active or active_version != target_version else 0


if __name__ == "__main__":
    raise SystemExit(main())
