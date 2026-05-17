#!/usr/bin/env python3
"""
Descarga assets NTI listados en sigma_nti_document y actualiza campos locales.

  python3 db/download_nti_sqlite.py --limit-rows 400
  python3 db/download_nti_sqlite.py                    # todas las filas pendientes

Reusa la lógica de sector_geometry/madrid_viso_docs_download (hosts permitidos, nombres de fichero).

Atención: miles de PDFs pueden ocupar decenas de GB y tardar horas; usa --limit-rows y --delay.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))
sys.path.insert(0, str(POC_ROOT))

from sqlite_assets import ensure_sigma_nti_asset_columns  # noqa: E402

from sector_geometry.madrid_viso_docs_download import (  # noqa: E402
    OUTPUT_DIR as NTI_OUTPUT_ROOT,
    _host_allowed,
    _norm_exp,
    _pick_filename,
    download_one,
)


DEFAULT_DB = DB_DIR / "poc_local.sqlite"


def main() -> None:
    ap = argparse.ArgumentParser(description="Descarga NTI en disco y marca SQLite.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit-rows", type=int, default=0, help="Máximo filas pendientes (0=todas).")
    ap.add_argument("--delay", type=float, default=0.35)
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--only-exp", nargs="*", default=[], help="Sólo estos expedientes (grupo ej. 135/2021/00618)")
    ap.add_argument(
        "--re-download-errors",
        action="store_true",
        help="También reintentar filas con download_error anterior",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Volver a bajar aunque local_path esté relleno",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"No existe {args.db}")

    want = {x.replace("_", "/").strip() for x in args.only_exp}

    with sqlite3.connect(args.db) as con:
        con.execute("PRAGMA foreign_keys = ON")
        ensure_sigma_nti_asset_columns(con)

        cond = [
            "url IS NOT NULL",
            "TRIM(url) != ''",
        ]
        if not args.force:
            cond.append("(local_path IS NULL OR TRIM(local_path) = '')")
        if not args.re_download_errors:
            cond.append("(download_error IS NULL OR TRIM(download_error) = '')")

        if want:
            cond.append(
                "expediente_grupo IN (" + ",".join("?" * len(want)) + ")"
            )

        sql = f"""
          SELECT id, expediente_grupo, orden, url, titulo, tooltip
          FROM sigma_nti_document
          WHERE {' AND '.join(cond)}
          ORDER BY expediente_grupo, orden
        """
        params: list[Any] = list(want) if want else []
        cur = con.execute(sql, params)
        rows = cur.fetchall()

    if args.limit_rows > 0:
        rows = rows[: args.limit_rows]

    ok = err = skip_host = 0
    for i, (rid, grupo, orden, url, titulo, tooltip) in enumerate(rows):
        parsed = urlparse(url)
        if not _host_allowed(parsed):
            with sqlite3.connect(args.db) as con2:
                ensure_sigma_nti_asset_columns(con2)
                con2.execute(
                    """
                    UPDATE sigma_nti_document SET
                      download_error = ?, http_status = NULL, downloaded_at = datetime('now')
                    WHERE id = ?
                    """,
                    ("host no permitido", rid),
                )
                con2.commit()
            skip_host += 1
            continue

        meta = {"titulo": titulo, "tooltip": tooltip}
        fname = _pick_filename(meta, url, int(orden) if orden is not None else i)
        dest = NTI_OUTPUT_ROOT / "madrid_nti_downloads" / _norm_exp(str(grupo)) / "files" / fname

        if args.delay > 0 and i > 0:
            time.sleep(args.delay)

        try:
            res = download_one(url, dest, timeout=args.timeout, retries=max(0, args.retries))
        except Exception as exc:
            res = {
                "ok": False,
                "httpStatus": None,
                "error": f"excepción: {exc}",
            }
        iso = datetime.now(timezone.utc).isoformat()

        if res.get("ok"):
            rel = res.get("savedPath")
            with sqlite3.connect(args.db) as con2:
                ensure_sigma_nti_asset_columns(con2)
                con2.execute(
                    """
                    UPDATE sigma_nti_document SET
                      local_path = ?, sha256 = ?, file_bytes = ?, content_type = ?,
                      http_status = ?, download_error = NULL, downloaded_at = ?
                    WHERE id = ?
                    """,
                    (
                        rel,
                        res.get("sha256"),
                        res.get("bytes"),
                        res.get("contentType"),
                        res.get("httpStatus"),
                        iso,
                        rid,
                    ),
                )
                con2.commit()
            ok += 1
        else:
            err_msg = str(res.get("error") or "fallo HTTP")
            with sqlite3.connect(args.db) as con2:
                ensure_sigma_nti_asset_columns(con2)
                con2.execute(
                    """
                    UPDATE sigma_nti_document SET
                      http_status = ?, download_error = ?, downloaded_at = ?
                    WHERE id = ?
                    """,
                    (res.get("httpStatus"), err_msg, iso, rid),
                )
                con2.commit()
            err += 1

    print(
        json.dumps(
            {
                "intentos": len(rows),
                "ok": ok,
                "fallos": err,
                "saltados_host": skip_host,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
