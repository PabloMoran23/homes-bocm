"""
Resolver Comunidad de Madrid: ámbitos de planeamiento (capa oficial SIT / GeoServer).

WFS: sitcm:VPLA_V_AMBITO (idem.comunidad.madrid/geoserver3).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .resolvers_builtin import (
    Resolution,
    SectorContext,
    centroid_from_geojson_obj,
)
from .resolvers_madrid_ayto import is_madrid_ciudad


WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
TYPE_NAME = "sitcm:VPLA_V_AMBITO"


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def _sector_ilike_parts(sector_raw: str) -> list[str]:
    """Partículas para DS_NOMB_AMB ILIKE '%p1%p2%…%' (tolerancia SUZ II-5 vs SUZ-II.5)."""
    s = sector_raw.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " del municipio", " (", "\n"):
        if marker in low:
            low = low.split(marker, 1)[0]
            break
    low = low.strip(" ,.;:|/")
    parts = [p for p in re.split(r"[\s,;/|]+", low) if p]
    out: list[str] = []
    for p in parts:
        for sub in re.split(r"[-–—]+", p):
            sub = sub.strip()
            if sub:
                out.append(sub)
    # quita duplicados conservando orden
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq[:12]


def _build_ilike_pattern(parts: list[str]) -> str:
    if not parts:
        return "%"
    return "%" + "%".join(_sql_escape(p) for p in parts) + "%"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _http_get_json(url: str, timeout: float = 60.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "poc-bocm-sector-geometry/0.1 (CM SIT WFS; +https://www.comunidad.madrid)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


class MadridSitcmAmbitoResolver:
    """
    bocm o CSV sin boletin_source_id; municipio_provincia suele contener «Madrid» (provincia).
    """

    id: str
    cfg: dict[str, Any]

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.id = str(cfg.get("id") or "madrid_sitcm_vpla_ambito")

    def accepts(self, ctx: SectorContext) -> bool:
        bid = (ctx.boletin_source_id or "").strip().lower()
        if bid and bid != "bocm":
            return False
        # Capital: capas Ayuntamiento (SIGMA/PGOUM), no SIT autonómico
        if is_madrid_ciudad(ctx):
            return False
        prov = (ctx.municipio_provincia_raw or "").lower()
        if self.cfg.get("require_provincia_madrid", True):
            if "madrid" not in prov:
                return False
        return True

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        parts = _sector_ilike_parts(ctx.sector_raw)
        if len(parts) < 1:
            return None
        pattern = _build_ilike_pattern(parts)
        muni = _sql_escape(ctx.municipio_raw.strip().upper())
        cql = f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'"
        count = int(self.cfg.get("count", 80))
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": TYPE_NAME,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{WFS_BASE}?{params}"
        data = _http_get_json(url)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            return None
        feats = data.get("features") or []
        if not feats:
            return None
        # Mejor candidato por nombre de ámbito más cercano al texto del sector
        sector_fold = re.sub(r"\s+", " ", ctx.sector_raw.lower())
        best_name: str | None = None
        best_score = -1.0
        by_name: dict[str, list[dict[str, Any]]] = {}
        for f in feats:
            if not isinstance(f, dict):
                continue
            p = f.get("properties") or {}
            name = str(p.get("DS_NOMB_AMB") or "")
            if not name:
                continue
            nf = name.lower().replace("–", "-")
            score = 0.0
            if nf in sector_fold or sector_fold in nf:
                score += 50
            for part in parts:
                if part.lower() in nf:
                    score += 5
            if score > best_score:
                best_score = score
                best_name = name
            by_name.setdefault(name, []).append(f)
        if best_name is None or best_name not in by_name:
            return None
        chosen = by_name[best_name]
        merged = _merge_geometries(chosen)
        if not merged:
            return None
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "geometry_scope": "cm_sitcm_vpla_ambito",
                        "DS_NOMB_AMB": best_name,
                        "DS_MUNICIPIO": chosen[0].get("properties", {}).get("DS_MUNICIPIO"),
                        "CD_MUNICIPIO": chosen[0].get("properties", {}).get("CD_MUNICIPIO"),
                        "n_features_merged": len(chosen),
                    },
                    "geometry": merged,
                }
            ],
        }
        c = centroid_from_geojson_obj(fc)
        if not c:
            return None
        lon, lat = c
        return Resolution(
            geometry_geojson=json.dumps(fc, ensure_ascii=False),
            centroid_lon=lon,
            centroid_lat=lat,
            resolver_id=self.id,
            detail={
                "geometry_scope": "cm_sitcm_vpla_ambito",
                "wfs_cql": cql[:400],
                "DS_NOMB_AMB": best_name,
                "n_features_merged": len(chosen),
                "query_url": url[:900],
            },
        )
