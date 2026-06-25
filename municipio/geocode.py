from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from municipio.geometry import geometry_bbox, geometry_centroid, has_area_geometry, record_geometry
from municipio.manifest import MUNICIPIOS_DIR, POC_ROOT, MunicipioManifest

COORDS_CACHE_PATH = POC_ROOT / "output" / "municipios_coords_cache.json"
JITTER_SPREAD_M = 180.0


def _load_coords_cache() -> dict[str, list[float]]:
    if not COORDS_CACHE_PATH.is_file():
        return {}
    raw = json.loads(COORDS_CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[float]] = {}
    for name, coords in raw.items():
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            out[str(name)] = [float(coords[0]), float(coords[1])]
    return out


def _record_coords(rec: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = rec.get("lat")
    lng = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    if lat is None or lng is None:
        return None, None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None


def _jitter(lat: float, lng: float, key: str, *, spread_m: float = JITTER_SPREAD_M) -> tuple[float, float]:
    """Desplaza ligeramente cada registro para no apilar todos en el centroide."""
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    angle = (h % 360) * math.pi / 180.0
    dist = ((h >> 8) % 1000) / 1000.0 * spread_m
    dlat = (dist * math.cos(angle)) / 111_320.0
    dlng = (dist * math.sin(angle)) / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lng + dlng


def _municipio_centroid(manifest: MunicipioManifest, cache: dict[str, list[float]]) -> tuple[float, float] | None:
    cfg = manifest.portal.config
    raw = cfg.get("centroid")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return float(raw[0]), float(raw[1])
        except (TypeError, ValueError):
            pass
    lat = cfg.get("centroid_lat")
    lng = cfg.get("centroid_lng") if cfg.get("centroid_lng") is not None else cfg.get("centroid_lon")
    if lat is not None and lng is not None:
        try:
            return float(lat), float(lng)
        except (TypeError, ValueError):
            pass
    for name in (manifest.nombre, manifest.slug.replace("-", " ").title()):
        if name in cache:
            lat, lng = cache[name]
            return lat, lng
    for key, coords in cache.items():
        if manifest.nombre.lower() in key.lower() or key.lower() in manifest.nombre.lower():
            return coords[0], coords[1]
    return None


def _geocode_records(
    records: list[dict[str, Any]],
    *,
    manifest: MunicipioManifest,
    cache: dict[str, list[float]],
) -> dict[str, int]:
    centroid = _municipio_centroid(manifest, cache)
    stats = {
        "explicit": 0,
        "from_geometry": 0,
        "jittered_centroid": 0,
        "missing_centroid": 0,
        "skipped": 0,
    }

    for rec in records:
        lat, lng = _record_coords(rec)
        rec_id = str(rec.get("id") or rec.get("licencia_key") or "")
        geom = record_geometry(rec)

        if geom and lat is None:
            centroid = geometry_centroid(geom)
            if centroid:
                lat, lng = centroid
                rec["geom_geojson"] = geom
                rec["lat"] = round(lat, 7)
                rec["lon"] = round(lng, 7)
                rec["lng"] = round(lng, 7)
                rec["coord_source"] = rec.get("coord_source") or "portal_geometry_centroid"
                stats["from_geometry"] += 1
                continue

        if lat is not None and lng is not None:
            stats["explicit"] += 1
            rec["lat"] = round(lat, 7)
            rec["lon"] = lng
            rec["lng"] = lng
            rec["coord_source"] = rec.get("coord_source") or "portal_explicit"
            if geom and not rec.get("geom_geojson"):
                rec["geom_geojson"] = geom
            continue

        if centroid is None:
            stats["missing_centroid"] += 1
            continue

        base_lat, base_lng = centroid
        if rec_id:
            lat, lng = _jitter(base_lat, base_lng, rec_id)
            stats["jittered_centroid"] += 1
        else:
            lat, lng = base_lat, base_lng
            stats["skipped"] += 1

        rec["lat"] = round(lat, 7)
        rec["lon"] = round(lng, 7)
        rec["lng"] = round(lng, 7)
        rec["coord_source"] = "municipio_centroid_jitter"

    return stats


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def geocode_manifest(manifest: MunicipioManifest) -> dict[str, Any]:
    manifest.ensure_output_dir()
    cache = _load_coords_cache()
    centroid = _municipio_centroid(manifest, cache)

    proyectos_path = manifest.output_dir / "proyectos.jsonl"
    licencias_path = manifest.output_dir / "licencias.jsonl"
    proyectos = _read_jsonl(proyectos_path)
    licencias = _read_jsonl(licencias_path)

    proy_stats = _geocode_records(proyectos, manifest=manifest, cache=cache)
    lic_stats = _geocode_records(licencias, manifest=manifest, cache=cache)

    if proyectos:
        _write_jsonl(proyectos_path, proyectos)
    if licencias:
        _write_jsonl(licencias_path, licencias)

    proy_with = sum(1 for r in proyectos if _record_coords(r)[0] is not None)
    lic_with = sum(1 for r in licencias if _record_coords(r)[0] is not None)
    proy_with_geom = sum(1 for r in proyectos if has_area_geometry(r))
    lic_with_geom = sum(1 for r in licencias if has_area_geometry(r))

    return {
        "status": "ok",
        "slug": manifest.slug,
        "nombre": manifest.nombre,
        "centroid": list(centroid) if centroid else None,
        "proyectos": {
            "rows": len(proyectos),
            "with_coords": proy_with,
            "with_geometry": proy_with_geom,
            **proy_stats,
        },
        "licencias": {
            "rows": len(licencias),
            "with_coords": lic_with,
            "with_geometry": lic_with_geom,
            **lic_stats,
        },
    }
