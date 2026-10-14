#!/usr/bin/env python3
"""Replay municipal semantic contracts, including rule changes, without rescraping.

Uses the same derivation as live ingestion, preserves immutable versions, skips
unchanged source/rules. Exceptions propagate and fail the scheduled job.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import connect, save_semantic_versions
from project_semantics import CONTRACT_VERSION, TEMPLATE_VERSION, apply, source_hash, source_record
from psycopg2.extras import Json, RealDictCursor


def replay(conn) -> dict[str, int]:
    counts = {"examined": 0, "reprocessed": 0, "discovered": 0}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT id, raw_features_json FROM homes.proyecto
                       WHERE municipio_slug IS NOT NULL
                         AND COALESCE(fuente, '') NOT IN ('sigma', 'bocm', 'bocm_legacy')
                       ORDER BY id FOR UPDATE""")
        records = cur.fetchall()
    for record in records:
        counts["examined"] += 1
        raw = record["raw_features_json"]
        if not isinstance(raw, dict):
            raise ValueError(f"{record['id']}: missing original municipal record")
        previous = raw.get("_semantic_contract", {})
        source = source_record(raw)
        if (previous.get("source_hash") == source_hash(source)
                and previous.get("contract_version") == CONTRACT_VERSION
                and previous.get("template_version") == TEMPLATE_VERSION):
            continue
        row = {"id": record["id"]}
        derived = apply(source, row)
        raw = {**source, "_semantic_contract": derived}
        with conn.cursor() as cur:
            save_semantic_versions(cur, [{**row, "raw_features_json": Json(raw)}])
            cur.execute("""UPDATE homes.proyecto SET fase=%s, fase_normalizada=%s,
                          fecha_aprob=%s, bocm_pub_date=%s, resumen_contenido=%s,
                          bocm_resumen=%s, raw_features_json=%s, updated_at=now()
                          WHERE id=%s""",
                        (row["fase"], row["fase_normalizada"], row["fecha_aprob"],
                         row["bocm_pub_date"], row["resumen_contenido"], row["bocm_resumen"],
                         Json(raw), row["id"]))
        counts["reprocessed"] += 1
        counts["discovered"] += derived["status"] == "discovered"
    return counts


if __name__ == "__main__":
    with connect() as connection:
        print(json.dumps(replay(connection), ensure_ascii=False))
