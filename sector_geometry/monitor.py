"""Resumen rápido de sector_geometry.sqlite3 (sin binario sqlite3)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("output/sector_geometry.sqlite3"))
    ap.add_argument("--samples", type=int, default=5, help="Filas matched a mostrar")
    args = ap.parse_args()
    if not args.db.is_file():
        print(f"No existe {args.db}", file=sys.stderr)
        return 1
    con = sqlite3.connect(str(args.db))
    con.row_factory = sqlite3.Row
    cur = con.execute(
        """
        SELECT status, COALESCE(last_error,'') AS err, COUNT(*) AS n
        FROM sector_spatial GROUP BY status, err ORDER BY n DESC
        """
    )
    rows = cur.fetchall()
    print("=== Por estado / error ===")
    for r in rows:
        print(f"  {r['status']:12} {r['err'][:60]!s:60} {r['n']}")
    cur = con.execute(
        """
        SELECT municipio_raw, sector_raw, boletin_source_id, resolver_id,
               centroid_lat, centroid_lon, match_detail_json
        FROM sector_spatial
        WHERE status = 'matched'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (args.samples,),
    )
    print("\n=== Últimos matched ===")
    for r in cur.fetchall():
        detail = {}
        if r["match_detail_json"]:
            try:
                detail = json.loads(r["match_detail_json"])
            except json.JSONDecodeError:
                detail = {}
        warn = detail.get("warning") or detail.get("geometry_scope") or ""
        print(
            f"  {r['municipio_raw']!r} | sector={r['sector_raw'][:55]!r}…\n"
            f"    fuente={r['boletin_source_id']} resolver={r['resolver_id']} "
            f"lat={r['centroid_lat']:.5f} lon={r['centroid_lon']:.5f}\n"
            f"    {warn}\n    nominatim: {detail.get('display_name', '')[:100]}"
        )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
