#!/usr/bin/env python3
"""Exporta ámbitos SIGMA (sigma_ambito_geom + catálogo) para el mapa web."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"
OUT_PATH = POC_ROOT / "web" / "public" / "data" / "madrid-sigma-ambitos.geojson"


def fecha_aprob_ms(fecha: str | None) -> int | None:
    if not fecha:
        return None
    s = str(fecha).strip()[:10]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def main() -> None:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT_PATH
    if not db.is_file():
        print(json.dumps({"error": f"No existe {db}. Ejecuta migrate + ingest_madrid_ubicacion."}))
        sys.exit(1)

    out.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT
          g.expediente_grupo,
          g.geom_geojson,
          c.exp_numero_original,
          c.denominacion,
          c.sigma_layer_kind,
          c.figura_codigo,
          c.fase,
          c.fecha_aprob,
          c.enlace,
          c.infopublica_inicio,
          c.infopublica_fin,
          (SELECT COUNT(DISTINCT l.licencia_id)
             FROM link_licencia_sigma l
            WHERE l.expediente_grupo = g.expediente_grupo) AS licencias_linked
        FROM sigma_ambito_geom g
        JOIN sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
        ORDER BY g.expediente_grupo
        """
    ).fetchall()

    features = []
    skipped = 0
    for r in rows:
        try:
            geom = json.loads(r["geom_geojson"])
        except (TypeError, json.JSONDecodeError):
            skipped += 1
            continue
        if not geom or not geom.get("type"):
            skipped += 1
            continue

        ms_aprob = fecha_aprob_ms(r["fecha_aprob"])
        props = {
            "EXP_TX_NUMERO": r["exp_numero_original"] or r["expediente_grupo"],
            "EXP_TX_DENOM": r["denominacion"],
            "FIG_TX_ETIQ": r["figura_codigo"],
            "FAS_TX_DENOM": r["fase"],
            "ENLACE": r["enlace"],
            "sigma_layer_kind": r["sigma_layer_kind"],
            "licencias_linked": r["licencias_linked"] or 0,
        }
        if ms_aprob is not None:
            props["FEX_DT_APROB"] = ms_aprob
        ip_ini = fecha_aprob_ms(r["infopublica_inicio"])
        ip_fin = fecha_aprob_ms(r["infopublica_fin"])
        if ip_ini is not None:
            props["FEX_DT_INFOPUB_INI"] = ip_ini
        if ip_fin is not None:
            props["FEX_DT_INFOPUB_FIN"] = ip_fin

        features.append({"type": "Feature", "geometry": geom, "properties": props})

    payload = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "features": len(features),
                "skipped": skipped,
                "out": str(out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
