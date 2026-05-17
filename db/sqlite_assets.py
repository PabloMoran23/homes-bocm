"""Utilidades DDL SQLite (columnas extra sin recrear tabla)."""

from __future__ import annotations

import sqlite3

_NTI_ASSET_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sha256", "TEXT"),
    ("file_bytes", "INTEGER"),
    ("content_type", "TEXT"),
    ("http_status", "INTEGER"),
    ("download_error", "TEXT"),
    ("downloaded_at", "TEXT"),
)


def ensure_sigma_nti_asset_columns(con: sqlite3.Connection) -> None:
    cur = con.execute("PRAGMA table_info(sigma_nti_document)")
    names = {str(r[1]) for r in cur.fetchall()}
    for name, ctype in _NTI_ASSET_COLUMNS:
        if name not in names:
            con.execute(f"ALTER TABLE sigma_nti_document ADD COLUMN {name} {ctype}")
