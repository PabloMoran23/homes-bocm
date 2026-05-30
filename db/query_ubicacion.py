#!/usr/bin/env python3
"""Consulta ficha de ubicación (inmueble + licencias + SIGMA) por NDP. Salida JSON stdout."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from geo_utils import point_in_geom

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
          c.fecha_aprob,
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

    expedientes_by_grupo: dict[str, dict] = {dict(r)["expediente_grupo"]: dict(r) for r in sigma_rows}

    lat, lng = inv["lat"], inv["lng"]
    if lat is not None and lng is not None:
        for row in con.execute(
            """
            SELECT g.expediente_grupo, g.geom_geojson,
                   c.exp_numero_original, c.sigma_layer_kind, c.denominacion, c.fase, c.enlace,
                   c.fecha_aprob, g.area_approx_m2
            FROM sigma_ambito_geom g
            JOIN sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
            WHERE g.bbox_min_lng <= ? AND g.bbox_max_lng >= ?
              AND g.bbox_min_lat <= ? AND g.bbox_max_lat >= ?
            ORDER BY COALESCE(g.area_approx_m2, 1e18) ASC
            """,
            (lng, lng, lat, lat),
        ):
            grupo = row["expediente_grupo"]
            if grupo in expedientes_by_grupo:
                continue
            try:
                geom = json.loads(row["geom_geojson"])
            except json.JSONDecodeError:
                continue
            if not point_in_geom(float(lng), float(lat), geom):
                continue
            expedientes_by_grupo[grupo] = {
                "expediente_grupo": grupo,
                "exp_numero_original": row["exp_numero_original"],
                "sigma_layer_kind": row["sigma_layer_kind"],
                "denominacion": row["denominacion"],
                "fase": row["fase"],
                "enlace": row["enlace"],
                "fecha_aprob": row.get("fecha_aprob"),
                "match_method": "point_in_edificio",
                "match_score": 1.0,
            }

    expedientes = sorted(
        expedientes_by_grupo.values(),
        key=lambda e: (e.get("sigma_layer_kind") or "", e.get("expediente_grupo") or ""),
    )

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
