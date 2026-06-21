#!/usr/bin/env python3
"""
Exporta proyectos y licencias de portales municipales CM → GeoJSON para el mapa web.

Uso:
  export SUPABASE_DB_URL=...
  python3 db/export_cm_portal_web.py [out_dir]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

DB_DIR = Path(__file__).resolve().parent
POC_ROOT = DB_DIR.parent
sys.path.insert(0, str(DB_DIR))

from sync_madrid_public_to_supabase import SCHEMA, pg_url  # noqa: E402

DEFAULT_OUT = POC_ROOT / "web" / "public" / "data"
CATALOG = "ayuntamiento-portal"


def _iso_date(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return str(v)[:10]
    return str(v)[:10]


def _feature(lng: float, lat: float, props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": props,
    }


def export_proyectos(cur, out_dir: Path, generated_at: str) -> int:
    cur.execute(
        f"""
        SELECT id, municipio, denominacion, bocm_title, bocm_pub_date, bocm_tipo_instrumento,
               enlace, visor_url, lat, lng, coord_source, sector_key, catalog_source
        FROM {SCHEMA}.proyecto
        WHERE catalog_source = %s
          AND lat IS NOT NULL AND lng IS NOT NULL
        ORDER BY municipio, bocm_pub_date DESC NULLS LAST, id
        """,
        (CATALOG,),
    )
    rows = list(cur.fetchall())
    features: list[dict[str, Any]] = []
    for r in rows:
        titulo = (r.get("bocm_title") or r.get("denominacion") or "").strip()
        features.append(
            _feature(
                float(r["lng"]),
                float(r["lat"]),
                {
                    "id": r["id"],
                    "municipio": r.get("municipio") or "",
                    "titulo": titulo,
                    "fecha": _iso_date(r.get("bocm_pub_date")),
                    "tipo": r.get("bocm_tipo_instrumento") or "",
                    "url": r.get("enlace") or r.get("visor_url") or "",
                    "coordSource": r.get("coord_source") or "",
                    "sectorKey": r.get("sector_key") or "",
                    "catalogSource": r.get("catalog_source") or CATALOG,
                },
            )
        )
    payload = {
        "type": "FeatureCollection",
        "generatedAt": generated_at,
        "features": features,
    }
    path = out_dir / "cm-portal-proyectos.geojson"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {path.name} ({len(features)} proyectos portal)")
    return len(features)


def export_licencias(cur, out_dir: Path, generated_at: str) -> int:
    cur.execute(
        f"""
        SELECT licencia_key, objeto, fecha_concesion, tipo_expediente, unidad, lat, lng, raw_json
        FROM {SCHEMA}.licencia
        WHERE lat IS NOT NULL AND lng IS NOT NULL
          AND COALESCE(raw_json->>'source', '') = 'ayuntamiento'
          AND COALESCE(raw_json->>'municipio_slug', '') <> ''
        ORDER BY fecha_concesion DESC NULLS LAST, licencia_key
        """
    )
    rows = list(cur.fetchall())
    features: list[dict[str, Any]] = []
    for r in rows:
        raw = r.get("raw_json") if isinstance(r.get("raw_json"), dict) else {}
        municipio = str(raw.get("municipio") or "")
        features.append(
            _feature(
                float(r["lng"]),
                float(r["lat"]),
                {
                    "id": str(r.get("licencia_key") or ""),
                    "municipio": municipio,
                    "titulo": (r.get("objeto") or "").strip(),
                    "fecha": _iso_date(r.get("fecha_concesion")),
                    "tipo": r.get("tipo_expediente") or "",
                    "distrito": r.get("unidad") or "",
                    "catalogSource": CATALOG,
                },
            )
        )
    payload = {
        "type": "FeatureCollection",
        "generatedAt": generated_at,
        "features": features,
    }
    path = out_dir / "cm-portal-licencias.geojson"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {path.name} ({len(features)} licencias portal)")
    return len(features)


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()

    with psycopg2.connect(pg_url()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            n_proy = export_proyectos(cur, out_dir, generated_at)
            n_lic = export_licencias(cur, out_dir, generated_at)

    if n_proy < 1:
        print("WARN: sin proyectos portal con coords", file=sys.stderr)
        return 1
    print(f"Export CM portal OK — {n_proy} proyectos, {n_lic} licencias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
