"""
Exporta filas `matched` de sector_geometry.sqlite3 a un GeoJSON para el visor web.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _first_geometry_from_stored_geojson(raw: str | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Devuelve (geometry, properties_merge) del primer feature guardado."""
    if not raw:
        return None, {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None, {}
    props: dict[str, Any] = {}
    geom: dict[str, Any] | None = None
    if obj.get("type") == "FeatureCollection":
        feats = obj.get("features") or []
        if feats and isinstance(feats[0], dict):
            f0 = feats[0]
            geom = f0.get("geometry") if isinstance(f0.get("geometry"), dict) else None
            if isinstance(f0.get("properties"), dict):
                props.update(f0["properties"])
    elif obj.get("type") == "Feature" and isinstance(obj.get("geometry"), dict):
        geom = obj["geometry"]
        if isinstance(obj.get("properties"), dict):
            props.update(obj["properties"])
    elif "type" in obj and "coordinates" in obj:
        geom = obj
    return geom, props


def export_map_geojson(
    db_path: Path | None = None,
    out_path: Path | None = None,
) -> tuple[int, Path]:
    """
    Escribe FeatureCollection en out_path (matched con geometría).
    Devuelve (n_features, out_path).
    """
    root = _repo_root()
    db = db_path or (root / "output" / "sector_geometry.sqlite3")
    out = out_path or (root / "output" / "sector_geometry_map.geojson")
    out.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    cur = con.execute(
        """
        SELECT stable_key, municipio_raw, sector_raw, municipio_provincia_raw, boletin_source_id,
               resolver_id, status, geometry_geojson, centroid_lon, centroid_lat, match_detail_json
        FROM sector_spatial
        WHERE status = 'matched' AND geometry_geojson IS NOT NULL
        ORDER BY updated_at DESC
        """
    )
    features: list[dict[str, Any]] = []
    for row in cur.fetchall():
        geom, gprops = _first_geometry_from_stored_geojson(row["geometry_geojson"])
        if not geom:
            continue
        detail: dict[str, Any] = {}
        if row["match_detail_json"]:
            try:
                detail = json.loads(row["match_detail_json"])
            except json.JSONDecodeError:
                pass
        props = {
            "stable_key": row["stable_key"],
            "municipio": row["municipio_raw"],
            "sector": row["sector_raw"],
            "provincia_linea": row["municipio_provincia_raw"],
            "boletin_source_id": row["boletin_source_id"],
            "resolver_id": row["resolver_id"],
            "DS_NOMB_AMB": detail.get("DS_NOMB_AMB"),
            "geometry_scope": detail.get("geometry_scope") or gprops.get("geometry_scope"),
        }
        features.append({"type": "Feature", "properties": props, "geometry": geom})

    fc = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    con.close()
    return len(features), out


def maybe_export_map(db: Path) -> None:
    """Si SECTOR_EXPORT_MAP_EACH_CYCLE=1, escribe output/sector_geometry_map.geojson."""
    raw = (os.getenv("SECTOR_EXPORT_MAP_EACH_CYCLE") or "").strip().lower()
    if raw not in ("1", "true", "yes", "si", "sí"):
        return
    try:
        n, p = export_map_geojson(db)
        print(f"[map-export] {n} features → {p}", flush=True)
    except Exception as ex:
        print(f"[map-export] error: {ex!r}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Exporta matched → output/sector_geometry_map.geojson")
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    n, p = export_map_geojson(args.db, args.out)
    print(f"Exportadas {n} geometrías → {p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
