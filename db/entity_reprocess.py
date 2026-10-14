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
from psycopg2.extras import Json, RealDictCursor

TABLES = {"proyecto": ("raw_features_json", "id"), "licencia": ("raw_json", "id")}


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
        cur.execute("UPDATE homes.entity_policy_config SET version=%s WHERE singleton AND version IS DISTINCT FROM %s",
                    (POLICY_VERSION, POLICY_VERSION))
        for table, (raw_col, _) in TABLES.items():
            cur.execute(f"""INSERT INTO homes.entity_reprocess_queue(entity_table, entity_id)
                SELECT %s, id::text FROM homes.{table}
                WHERE {raw_col}->%s->>'version' IS DISTINCT FROM %s
                ON CONFLICT (entity_table, entity_id) DO NOTHING""", (table, POLICY_KEY, POLICY_VERSION))


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
                    derived = annotate(source_record(row, entity_table), kind=entity_table)
                    metadata = derived[POLICY_KEY]
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
            cur.execute("""SELECT count(*) FROM homes.proyecto_actividad
                WHERE raw_features_json->'_entity_policy'->>'entity_type' NOT IN ('actuacion','expediente')""")
            invalid = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM homes.licencia_actividad
                WHERE raw_json->'_entity_policy'->>'entity_type' NOT IN ('actuacion','expediente')
                OR raw_json->'_entity_policy'->>'grant_evidenced' IS DISTINCT FROM 'true'""")
            invalid += cur.fetchone()[0]
        print(json.dumps({**total, "version": POLICY_VERSION, "backlog": backlog, "invalid_activity": invalid}))
    return 1 if total["failed"] or backlog or invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
