"""Fail-closed geography normalization, shared by pipeline and direct DB ingestion.

Original fields survive quarantine. An unchanged derivative is replayed from those
originals on every invocation, including after rule/CRS configuration changes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform, unary_union

from municipio.geometry import record_geometry

RULE_VERSION = "h03-v1"
FIELDS = ("geom_geojson", "geometry", "geom", "lat", "lon", "lng", "centroid_lat", "centroid_lng",
          "bbox_min_lng", "bbox_min_lat", "bbox_max_lng", "bbox_max_lat", "coord_source")


def _safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(_safe(value), sort_keys=True, default=str).encode()).hexdigest()


def valid_coordinates(lat: Any, lng: Any) -> bool:
    try:
        if isinstance(lat, bool) or isinstance(lng, bool):
            return False
        lat, lng = float(lat), float(lng)
        return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180
    except (ValueError, TypeError):
        return False


def normalize_geometry(geometry: dict, crs: Any, axis_order: str = "xy") -> dict:
    if not crs:
        raise ValueError("unknown_crs")
    if axis_order not in ("xy", "yx"):
        raise ValueError("unknown_axis_order")
    transformer = Transformer.from_crs(CRS.from_user_input(crs), CRS.from_epsg(4326), always_xy=True)

    def convert(x, y, z=None):
        if axis_order == "yx":
            x, y = y, x
        return transformer.transform(x, y, errcheck=True)

    # Shapely auto-closes rings: reject malformed originals instead of repairing them.
    def check(node):
        if not isinstance(node, (list, tuple)) or not node:
            raise ValueError("invalid_coordinates")
        if isinstance(node[0], (int, float)):
            if len(node) < 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in node):
                raise ValueError("nonfinite_coordinates")
        else:
            for child in node:
                check(child)

    check(geometry.get("coordinates"))
    kind = geometry.get("type")
    if kind not in ("Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"):
        raise ValueError("unsupported_geometry")
    polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"] if kind == "MultiPolygon" else []
    for polygon in polygons:
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("unclosed_ring")
    geo = transform(convert, shape(geometry))
    if geo.is_empty or not geo.is_valid:
        raise ValueError("invalid_topology")
    x0, y0, x1, y1 = geo.bounds
    if not valid_coordinates(y0, x0) or not valid_coordinates(y1, x1):
        raise ValueError("outside_wgs84")
    # Dataset territory includes the Canaries, Balearics, Ceuta and Melilla.
    if not (-19 <= x0 <= x1 <= 5 and 27 <= y0 <= y1 <= 44):
        raise ValueError("outside_spain")
    return json.loads(json.dumps(mapping(geo)))


@lru_cache(maxsize=512)
def official_boundary(name: str) -> dict | None:
    """IGN OGC API returns RFC7946 (longitude, latitude); exact name only.

    Failures are not evidence of a location. No nearest-municipality selection.
    Cache is per process/run, so recurring ingestion refreshes the evidence.
    """
    if not name:
        return None
    query = urllib.parse.urlencode({"f": "json", "limit": "100", "nationallevelname": "Municipio", "nameunit": name})
    url = "https://api-features.ign.es/collections/administrativeunit/items?" + query
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.load(response)
        features = [f for f in data.get("features", []) if str(f.get("properties", {}).get("nameunit", "")).casefold() == name.casefold()]
        if len(features) == 1:
            return {"geometry": features[0]["geometry"], "source": url, "crs": "EPSG:4326", "axis_order": "xy"}
    except Exception:
        pass
    return None


def manifest_geography_config(manifest) -> dict:
    from municipio.manifest import load_yaml
    data = load_yaml(manifest.path)
    return dict(data.get("geometry", {}).get("validation", {}))


def normalize_record(rec: dict[str, Any], *, cfg: dict | None = None, municipality: str = "", fetch_boundary: bool = False) -> dict:
    """Returns a copy, never mutates source records or publishes unchecked fields."""
    cfg = cfg or {}
    out = copy.deepcopy(rec)
    current = {k: rec[k] for k in FIELDS if k in rec}
    prior = rec.get("geography_validation") or {}
    if prior.get("output_hash") == _hash(current) and isinstance(rec.get("geography_original"), dict):
        original = copy.deepcopy(rec["geography_original"])
    else:
        original = _safe(current)
        # The migration quarantines invalid canonical legacy fields transactionally.
        # Replay that retained evidence when no newer geographic source exists.
        quarantine = rec.get("_geography_quarantine") or {}
        saved = quarantine.get("original") if isinstance(quarantine, dict) else None
        if isinstance(saved, dict) and not any(current.get(k) is not None for k in FIELDS if k != "coord_source"):
            original = _safe({k: saved[k] for k in FIELDS if k in saved})
    out["geography_original"] = original
    working = {**rec, **original}
    for k in FIELDS:
        out.pop(k, None)
    crs = cfg.get("source_crs") or rec.get("geometry_crs") or rec.get("source_crs")
    order = cfg.get("axis_order") or rec.get("geometry_axis_order") or "xy"
    geom = record_geometry(working)
    # A legacy GeoJSON CRS declaration is evidence, never infer from magnitude.
    if not crs and geom:
        raw = next((working.get(k) for k in ("geom_geojson", "geometry", "geom") if isinstance(working.get(k), dict)), {})
        crs = (raw.get("crs") or {}).get("properties", {}).get("name")
    coordinate_crs = cfg.get("coordinates_crs") or rec.get("coordinates_crs") or cfg.get("source_crs") or rec.get("source_crs")
    boundaries = cfg.get("municipal_boundaries") or rec.get("municipal_boundaries") or {}
    boundary = cfg.get("municipal_boundary") or rec.get("municipal_boundary")
    can_transform = bool(geom and crs) or bool(not geom and coordinate_crs and any(original.get(k) is not None for k in ("lat", "lon", "lng")))
    if not boundary and fetch_boundary and can_transform:
        boundary = official_boundary(municipality)
    if boundary:
        boundaries = {**boundaries, municipality: boundary}
        out["municipal_boundary"] = boundary
    scope = rec.get("municipality_scope") or [municipality]
    if not isinstance(scope, list) or not scope or any(not isinstance(name, str) or not name for name in scope):
        scope = [municipality]
    errors = {}
    if geom is None and any(original.get(k) is not None for k in ("geom_geojson", "geometry", "geom")):
        errors["geometry"] = "invalid_or_unsupported_geometry_structure"
    targets = []
    for name in scope:
        b = boundaries.get(name)
        if b:
            try:
                targets.append(shape(normalize_geometry(b.get("geometry", b), b.get("crs", "EPSG:4326"), b.get("axis_order", "xy"))))
            except Exception:
                pass
    territory = unary_union(targets) if len(targets) == len(scope) and targets else None
    multi = len(scope) > 1 and bool(rec.get("multimunicipal_evidence")) and municipality in scope

    def municipal_check(g):
        if not municipality or municipality not in scope:
            raise ValueError("ingest_municipality_outside_scope")
        if territory is None:
            raise ValueError("municipal_boundary_unavailable")
        if len(scope) > 1 and not multi:
            raise ValueError("multimunicipal_evidence_required")
        if not territory.covers(g):
            raise ValueError("outside_municipality_scope")

    if geom:
        try:
            normalized = normalize_geometry(geom, crs, order)
            municipal_check(shape(normalized))
            out["geom_geojson"] = normalized
            geo = shape(normalized)
            point = geo.centroid
            method = "centroid"
            if not geo.covers(point):
                point = geo.representative_point()
                method = "point_on_surface"
            out["geometry_location_method"] = method
            out.update(lat=point.y, lng=point.x, lon=point.x, centroid_lat=point.y, centroid_lng=point.x,
                       coord_source="portal_geometry_" + method)
            x0, y0, x1, y1 = shape(normalized).bounds
            out.update(bbox_min_lng=x0, bbox_min_lat=y0, bbox_max_lng=x1, bbox_max_lat=y1)
        except Exception as exc:
            errors["geometry"] = str(exc)
    lat = original.get("lat")
    lng = original.get("lon") if original.get("lon") is not None else original.get("lng")
    # Geometry-derived coordinates must be regenerated from the original geometry.
    if (lat is not None or lng is not None) and "geometry" not in errors and not geom:
        try:
            coord_crs = coordinate_crs
            if not coord_crs:
                raise ValueError("unknown_coordinate_crs")
            coord_order = cfg.get("coordinates_axis_order") or rec.get("coordinates_axis_order") or cfg.get("axis_order") or "xy"
            p = normalize_geometry({"type": "Point", "coordinates": [float(lng), float(lat)]}, coord_crs, coord_order)
            municipal_check(shape(p))
            x, y = p["coordinates"]
            out.update(lat=y, lng=x, lon=x, coord_source=original.get("coord_source") or "portal_explicit")
        except Exception as exc:
            errors["coordinates"] = str(exc)
    out["has_geometry"] = bool(out.get("geom_geojson"))
    validation = {"rule_version": RULE_VERSION, "source_crs": str(crs) if crs else None, "target_crs": "EPSG:4326",
                  "coordinate_source_crs": coordinate_crs,
                  "axis_order": order, "config_hash": _hash(cfg), "input_hash": _hash(original), "errors": errors,
                  "status": "quarantined" if errors else "valid" if out.get("lat") is not None else "unlocated",
                  "municipality_scope": scope, "boundary_hash": _hash(boundaries)}
    validation["output_hash"] = _hash({k: out[k] for k in FIELDS if k in out})
    out["geography_validation"] = validation
    return out
