from __future__ import annotations

from typing import Any


def record_geometry(rec: dict[str, Any]) -> dict[str, Any] | None:
    """GeoJSON Geometry o Feature/FeatureCollection embebido en un registro portal."""
    for key in ("geom_geojson", "geometry", "geom"):
        raw = rec.get(key)
        if isinstance(raw, dict) and raw.get("type"):
            gtype = str(raw["type"])
            if gtype == "Feature":
                geom = raw.get("geometry")
                return geom if isinstance(geom, dict) else None
            if gtype == "FeatureCollection":
                feats = raw.get("features") or []
                if feats and isinstance(feats[0], dict):
                    geom = feats[0].get("geometry")
                    return geom if isinstance(geom, dict) else None
            if gtype in {"Point", "LineString", "Polygon", "MultiPolygon", "MultiPoint"}:
                return raw
    return None


def has_area_geometry(rec: dict[str, Any]) -> bool:
    geom = record_geometry(rec)
    if not geom:
        return False
    return str(geom.get("type") or "") in {"Polygon", "MultiPolygon"}


def _walk_coords(node: Any, lngs: list[float], lats: list[float]) -> None:
    if isinstance(node, (list, tuple)):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            lngs.append(float(node[0]))
            lats.append(float(node[1]))
            return
        for item in node:
            _walk_coords(item, lngs, lats)


def geometry_bbox(geom: dict[str, Any]) -> tuple[float, float, float, float] | None:
    lngs: list[float] = []
    lats: list[float] = []
    _walk_coords(geom.get("coordinates"), lngs, lats)
    if not lngs:
        return None
    return min(lngs), min(lats), max(lngs), max(lats)


def geometry_centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    bbox = geometry_bbox(geom)
    if not bbox:
        return None
    min_lng, min_lat, max_lng, max_lat = bbox
    return (min_lat + max_lat) / 2.0, (min_lng + max_lng) / 2.0
