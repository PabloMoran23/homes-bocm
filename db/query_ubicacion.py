#!/usr/bin/env python3
"""Consulta ficha de ubicación (inmueble + licencias + SIGMA) por NDP. Salida JSON stdout."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"


def query(con: sqlite3.Connection, ndp: str) -> dict | None:
    inv = con.execute(
        "SELECT * FROM inmueble WHERE ndp_edificio = ?", (ndp,)
    ).fetchone()
    if not inv:
        return None

    licencias = [
        dict(r)
        for r in con.execute(
            """
            SELECT id, licencia_key, anio_dataset, fecha_alta, fecha_concesion,
                   procedimiento, tipo_expediente, uso, interesado, objeto, unidad
            FROM actuacion_edificacion
            WHERE inmueble_id = ?
            ORDER BY fecha_concesion DESC, fecha_alta DESC
            LIMIT 200
            """,
            (inv["id"],),
        )
    ]

    sigma_rows = con.execute(
        """
        SELECT DISTINCT
          c.expediente_grupo,
          c.exp_numero_original,
          c.sigma_layer_kind,
          c.denominacion,
          c.fase,
          c.enlace,
          l.match_method,
          l.match_score
        FROM actuacion_edificacion ae
        JOIN link_licencia_sigma l ON l.licencia_id = ae.id
        JOIN sigma_catalog_expediente c ON c.expediente_grupo = l.expediente_grupo
        WHERE ae.inmueble_id = ?
        ORDER BY c.sigma_layer_kind, c.expediente_grupo
        """,
        (inv["id"],),
    ).fetchall()

    expedientes = [dict(r) for r in sigma_rows]

    tramites: dict[str, list] = {}
    for exp in expedientes:
        grp = exp["expediente_grupo"]
        rows = con.execute(
            """
            SELECT fecha, tramite, organo
            FROM sigma_vis_tramite
            WHERE expediente_grupo = ?
            ORDER BY orden
            """,
            (grp,),
        ).fetchall()
        if rows:
            tramites[grp] = [dict(r) for r in rows]

    return {
        "inmueble": dict(inv),
        "licencias": licencias,
        "expedientesSigma": expedientes,
        "tramitacionSigma": tramites,
        "stats": {
            "licenciasTotal": len(licencias),
            "expedientesSigma": len(expedientes),
        },
    }


def main() -> None:
    ndp = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB
    if not ndp:
        print(json.dumps({"error": "ndp requerido"}))
        sys.exit(1)
    if not db.is_file():
        print(json.dumps({"error": f"db no encontrada: {db}"}))
        sys.exit(1)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    data = query(con, ndp)
    if not data:
        print(json.dumps({"error": "not_found", "ndp": ndp}))
        sys.exit(2)
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
