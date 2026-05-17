#!/usr/bin/env python3
"""Genera SQL por lotes para tablas medianas (uso manual / MCP execute_sql)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"
BATCH = 40


def esc(s) -> str:
    if s is None:
        return "NULL"
    if isinstance(s, bool):
        return "true" if s else "false"
    if isinstance(s, (int, float)):
        return str(s)
    return "'" + str(s).replace("'", "''") + "'"


def main() -> None:
    table = sys.argv[1] if len(sys.argv) > 1 else "sigma_catalog_expediente"
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    if table == "sigma_catalog_expediente":
        rows = list(con.execute("SELECT * FROM sigma_catalog_expediente ORDER BY expediente_grupo"))
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            vals = []
            for r in chunk:
                vals.append(
                    f"({esc(r['expediente_grupo'])},{esc(r['exp_numero_original'])},"
                    f"{esc(r['sigma_layer_kind'])},{esc(r['denominacion'])},{esc(r['fase'])},"
                    f"{esc(r['fecha_aprob'])},{esc(r['infopublica_inicio'])},{esc(r['infopublica_fin'])},"
                    f"{esc(r['figura_codigo'])},{esc(r['tipo_figura'])},{esc(r['organo_tramitador'])},"
                    f"{esc(r['enlace'])},{esc(r['catalog_source'])},{esc(r['object_id'])},"
                    f"{esc(bool(r['has_geometry']))},{esc(r['synced_at'])},NULL)"
                )
            sql = (
                "INSERT INTO homes.sigma_catalog_expediente "
                "(expediente_grupo,exp_numero_original,sigma_layer_kind,denominacion,fase,"
                "fecha_aprob,infopublica_inicio,infopublica_fin,figura_codigo,tipo_figura,"
                "organo_tramitador,enlace,catalog_source,object_id,has_geometry,synced_at,raw_features_json) "
                f"VALUES {','.join(vals)} ON CONFLICT (expediente_grupo) DO NOTHING;"
            )
            print(f"-- batch {i // BATCH + 1}")
            print(sql)
    else:
        print(f"Tabla no soportada: {table}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
