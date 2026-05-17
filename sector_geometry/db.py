from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS sector_spatial (
    stable_key TEXT PRIMARY KEY,
    municipio_raw TEXT,
    sector_raw TEXT,
    municipio_norm TEXT NOT NULL,
    sector_norm TEXT NOT NULL,
    municipio_provincia_raw TEXT,
    boletin_source_id TEXT,
    proyecto_fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    geometry_geojson TEXT,
    centroid_lon REAL,
    centroid_lat REAL,
    resolver_id TEXT,
    match_detail_json TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_attempt_at REAL
);

CREATE INDEX IF NOT EXISTS idx_sector_spatial_status
ON sector_spatial(status);

CREATE INDEX IF NOT EXISTS idx_sector_spatial_municipio_norm
ON sector_spatial(municipio_norm);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.executescript(SCHEMA)
    return con


def now_ts() -> float:
    return time.time()


def upsert_pending(
    con: sqlite3.Connection,
    *,
    stable_key: str,
    municipio_raw: str | None,
    sector_raw: str | None,
    municipio_norm: str,
    sector_norm: str,
    municipio_provincia_raw: str | None,
    boletin_source_id: str | None,
    proyecto_fingerprint: str | None,
) -> str:
    """Inserta pendiente si no existe. Devuelve 'inserted' | 'exists'."""
    ts = now_ts()
    cur = con.execute(
        """
        INSERT INTO sector_spatial (
            stable_key, municipio_raw, sector_raw, municipio_norm, sector_norm,
            municipio_provincia_raw, boletin_source_id, proyecto_fingerprint,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        ON CONFLICT(stable_key) DO NOTHING
        """,
        (
            stable_key,
            municipio_raw,
            sector_raw,
            municipio_norm,
            sector_norm,
            municipio_provincia_raw,
            boletin_source_id,
            proyecto_fingerprint,
            ts,
            ts,
        ),
    )
    con.commit()
    return "inserted" if cur.rowcount else "exists"


def fetch_next_pending(con: sqlite3.Connection) -> sqlite3.Row | None:
    cur = con.execute(
        """
        SELECT * FROM sector_spatial
        WHERE status = 'pending'
        ORDER BY
          CASE
            WHEN municipio_provincia_raw IS NOT NULL
             AND instr(lower(municipio_provincia_raw), 'madrid') > 0 THEN 0
            ELSE 1
          END,
          created_at ASC
        LIMIT 1
        """
    )
    return cur.fetchone()


def mark_result(
    con: sqlite3.Connection,
    stable_key: str,
    *,
    status: str,
    geometry_geojson: str | None = None,
    centroid_lon: float | None = None,
    centroid_lat: float | None = None,
    resolver_id: str | None = None,
    match_detail: dict[str, Any] | None = None,
    last_error: str | None = None,
    increment_attempt: bool = True,
) -> None:
    ts = now_ts()
    detail_json = json.dumps(match_detail, ensure_ascii=False) if match_detail else None
    if increment_attempt:
        con.execute(
            """
            UPDATE sector_spatial SET
                status = ?,
                geometry_geojson = COALESCE(?, geometry_geojson),
                centroid_lon = COALESCE(?, centroid_lon),
                centroid_lat = COALESCE(?, centroid_lat),
                resolver_id = COALESCE(?, resolver_id),
                match_detail_json = COALESCE(?, match_detail_json),
                last_error = ?,
                attempt_count = attempt_count + 1,
                last_attempt_at = ?,
                updated_at = ?
            WHERE stable_key = ?
            """,
            (
                status,
                geometry_geojson,
                centroid_lon,
                centroid_lat,
                resolver_id,
                detail_json,
                last_error,
                ts,
                ts,
                stable_key,
            ),
        )
    else:
        con.execute(
            """
            UPDATE sector_spatial SET
                status = ?,
                geometry_geojson = COALESCE(?, geometry_geojson),
                centroid_lon = COALESCE(?, centroid_lon),
                centroid_lat = COALESCE(?, centroid_lat),
                resolver_id = COALESCE(?, resolver_id),
                match_detail_json = COALESCE(?, match_detail_json),
                last_error = ?,
                updated_at = ?
            WHERE stable_key = ?
            """,
            (
                status,
                geometry_geojson,
                centroid_lon,
                centroid_lat,
                resolver_id,
                detail_json,
                last_error,
                ts,
                stable_key,
            ),
        )
    con.commit()
