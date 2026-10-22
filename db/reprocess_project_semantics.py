#!/usr/bin/env python3
"""Replay municipal semantic contracts, including rule changes, without rescraping.

Uses the same derivation as live ingestion, preserves immutable versions, skips
unchanged source/rules. Reads and commits in batches so a daily run does not
lock the table for the whole census. Exceptions fail the current batch; batches
already committed stay done and the next run continues.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import connect, save_semantic_versions
from project_semantics import CONTRACT_VERSION, TEMPLATE_VERSION, apply, source_hash, source_record
from psycopg2.extras import Json, RealDictCursor

BATCH_SIZE = 200


def replay(conn, *, batch_size: int = BATCH_SIZE, commit_batches: bool = False) -> dict[str, int]:
    counts = {"examined": 0, "reprocessed": 0, "discovered": 0}
    last_id = ""
    while True:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, raw_features_json FROM homes.proyecto
                   WHERE municipio_slug IS NOT NULL
                     AND COALESCE(fuente, '') NOT IN ('sigma', 'bocm', 'bocm_legacy')
                     AND id > %s
                   ORDER BY id
                   LIMIT %s""",
                (last_id, batch_size),
            )
            records = cur.fetchall()
        if not records:
            break
        last_id = records[-1]["id"]
        pending: list[dict] = []
        for record in records:
            counts["examined"] += 1
            raw = record["raw_features_json"]
            if not isinstance(raw, dict):
                raise ValueError(f"{record['id']}: missing original municipal record")
            previous = raw.get("_semantic_contract") or {}
            source = source_record(raw)
            if (
                previous.get("source_hash") == source_hash(source)
                and previous.get("contract_version") == CONTRACT_VERSION
                and previous.get("template_version") == TEMPLATE_VERSION
            ):
                continue
            row = {"id": record["id"]}
            derived = apply(source, row)
            pending.append({**row, "raw_features_json": Json({**source, "_semantic_contract": derived})})
            counts["reprocessed"] += 1
            counts["discovered"] += derived["status"] == "discovered"
        if pending:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM homes.proyecto WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                    ([row["id"] for row in pending],),
                )
                save_semantic_versions(cur, pending)
                cur.executemany(
                    """UPDATE homes.proyecto SET fase=%s, fase_normalizada=%s,
                       fecha_aprob=%s, bocm_pub_date=%s, resumen_contenido=%s,
                       bocm_resumen=%s, raw_features_json=%s, updated_at=now()
                       WHERE id=%s""",
                    [
                        (
                            row["fase"],
                            row["fase_normalizada"],
                            row["fecha_aprob"],
                            row["bocm_pub_date"],
                            row["resumen_contenido"],
                            row["bocm_resumen"],
                            row["raw_features_json"],
                            row["id"],
                        )
                        for row in pending
                    ],
                )
        if commit_batches:
            conn.commit()
            print(json.dumps({**counts, "last_id": last_id}), flush=True)
    return counts


if __name__ == "__main__":
    with connect() as connection:
        print(json.dumps(replay(connection, commit_batches=True), ensure_ascii=False))
