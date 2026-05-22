#!/usr/bin/env python3
"""Exporta sigma_expediente_metric → web/public/data/madrid-sigma-metrics.json"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sector_geometry.madrid_nti_vivienda_sanity import sanitize_viviendas_en_metrics


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "poc_local.sqlite"
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(__file__).resolve().parent.parent / "web" / "public" / "data" / "madrid-sigma-metrics.json"
    )
    if not db_path.is_file():
        print(f"no db: {db_path}", file=sys.stderr)
        return 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM sigma_expediente_metric").fetchall()
    by: dict[str, dict] = {}
    for r in rows:
        hechos: list = []
        if r["hechos_json"]:
            try:
                raw = json.loads(r["hechos_json"])
                hechos = raw[:6] if isinstance(raw, list) else []
            except json.JSONDecodeError:
                pass
        tipo_vivienda = None
        if r["metrics_json"]:
            try:
                mj = json.loads(r["metrics_json"])
                if isinstance(mj, dict):
                    tipo_vivienda = mj.get("tipo_vivienda")
            except json.JSONDecodeError:
                pass
        row = sanitize_viviendas_en_metrics(
            {
                "num_viviendas_max": r["num_viviendas_max"],
                "sup_total_m2": r["sup_total_m2"],
                "sup_edificable_m2": r["sup_edificable_m2"],
                "tipo_vivienda": tipo_vivienda,
                "genera_vivienda_nueva": r["genera_vivienda_nueva"],
                "familia_expediente": r["familia_expediente"],
                "pdfs_procesados": r["pdfs_procesados"],
                "doc_role_principal": r["doc_role_principal"],
                "hechos": hechos,
            }
        )
        by[r["expediente_grupo"]] = row

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(by),
        "byExpediente": by,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {out_path} ({len(by)} expedientes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
