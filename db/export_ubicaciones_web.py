#!/usr/bin/env python3
"""Exporta inmuebles Madrid para el mapa de exploración (web/public/data)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from direccion import normalize_direccion
from geo_utils import is_valid_wgs84_madrid

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = POC_ROOT / "db" / "poc_local.sqlite"
OUT_DIR = POC_ROOT / "web" / "public" / "data"
MAP_GEOJSON = OUT_DIR / "ubicaciones-map.geojson"
SEARCH_JSON = OUT_DIR / "ubicaciones-search.json"
META_JSON = OUT_DIR / "ubicaciones-meta.json"


def fecha_es_a_iso(raw: str | None) -> str | None:
    """Convierte D/M/YYYY o ISO a YYYY-MM-DD para el cliente."""
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    parts = s.split("/")
    if len(parts) == 3:
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000 if y < 50 else 1900
            return f"{y:04d}-{m:02d}-{d:02d}"
        except ValueError:
            return None
    return None


def main() -> None:
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.is_file():
        print(json.dumps({"error": f"No existe {db}. Ejecuta migrate + ingest_madrid_ubicacion."}))
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        """
        SELECT
          i.ndp_edificio,
          i.direccion,
          i.distrito,
          i.barrio,
          i.lat,
          i.lng,
          (SELECT COUNT(*) FROM actuacion_edificacion ae WHERE ae.inmueble_id = i.id) AS licencias_count,
          (SELECT COUNT(DISTINCT l.expediente_grupo)
             FROM actuacion_edificacion ae
             JOIN link_licencia_sigma l ON l.licencia_id = ae.id
            WHERE ae.inmueble_id = i.id) AS sigma_count,
          (SELECT ae.tipo_expediente
             FROM actuacion_edificacion ae
            WHERE ae.inmueble_id = i.id
            ORDER BY
              CASE WHEN ae.fecha_concesion IS NULL OR ae.fecha_concesion = '' THEN 1 ELSE 0 END,
              ae.fecha_concesion DESC,
              ae.fecha_alta DESC
            LIMIT 1) AS ultima_licencia_tipo,
          (SELECT ae.objeto
             FROM actuacion_edificacion ae
            WHERE ae.inmueble_id = i.id
            ORDER BY
              CASE WHEN ae.fecha_concesion IS NULL OR ae.fecha_concesion = '' THEN 1 ELSE 0 END,
              ae.fecha_concesion DESC,
              ae.fecha_alta DESC
            LIMIT 1) AS ultima_licencia_objeto,
          (SELECT ae.uso
             FROM actuacion_edificacion ae
            WHERE ae.inmueble_id = i.id
            ORDER BY
              CASE WHEN ae.fecha_concesion IS NULL OR ae.fecha_concesion = '' THEN 1 ELSE 0 END,
              ae.fecha_concesion DESC,
              ae.fecha_alta DESC
            LIMIT 1) AS ultima_licencia_uso,
          (SELECT ae.procedimiento
             FROM actuacion_edificacion ae
            WHERE ae.inmueble_id = i.id
            ORDER BY
              CASE WHEN ae.fecha_concesion IS NULL OR ae.fecha_concesion = '' THEN 1 ELSE 0 END,
              ae.fecha_concesion DESC,
              ae.fecha_alta DESC
            LIMIT 1) AS ultima_licencia_procedimiento,
          (SELECT COALESCE(NULLIF(ae.fecha_concesion, ''), ae.fecha_alta)
             FROM actuacion_edificacion ae
            WHERE ae.inmueble_id = i.id
            ORDER BY
              CASE WHEN ae.fecha_concesion IS NULL OR ae.fecha_concesion = '' THEN 1 ELSE 0 END,
              ae.fecha_concesion DESC,
              ae.fecha_alta DESC
            LIMIT 1) AS ultima_licencia_fecha
        FROM inmueble i
        WHERE i.lat IS NOT NULL AND i.lng IS NOT NULL
        ORDER BY licencias_count DESC
        """
    ).fetchall()

    features = []
    search = []
    skipped_invalid = 0
    for r in rows:
        ndp = r["ndp_edificio"]
        lat, lng = float(r["lat"]), float(r["lng"])
        if not is_valid_wgs84_madrid(lng, lat):
            skipped_invalid += 1
            continue
        direccion = normalize_direccion(r["direccion"])
        props = {
            "ndp": ndp,
            "direccion": direccion,
            "distrito": r["distrito"],
            "barrio": r["barrio"],
            "licencias": r["licencias_count"],
            "sigma": r["sigma_count"],
            "ultimaLicenciaTipo": r["ultima_licencia_tipo"],
            "ultimaLicenciaObjeto": r["ultima_licencia_objeto"],
            "ultimaLicenciaUso": r["ultima_licencia_uso"],
            "ultimaLicenciaProcedimiento": r["ultima_licencia_procedimiento"],
            "ultimaLicenciaFecha": fecha_es_a_iso(r["ultima_licencia_fecha"]),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": props,
            }
        )
        search.append(
            {
                "ndp": ndp,
                "direccion": direccion or "",
                "distrito": r["distrito"] or "",
                "barrio": r["barrio"] or "",
                "label": " · ".join(
                    p
                    for p in [direccion, r["distrito"], f"NDP {ndp}"]
                    if p
                ),
            }
        )

    MAP_GEOJSON.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    SEARCH_JSON.write_text(json.dumps(search, ensure_ascii=False), encoding="utf-8")
    META_JSON.write_text(
        json.dumps(
            {
                "generatedAt": __import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ).isoformat(),
                "inmueblesConCoords": len(features),
                "skippedInvalidCoords": skipped_invalid,
                "db": str(db),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "inmuebles": len(features),
                "skippedInvalidCoords": skipped_invalid,
                "map": str(MAP_GEOJSON),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
