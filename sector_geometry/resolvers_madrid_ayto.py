"""
Resolvers Ayuntamiento de Madrid (SIGMA / PGOUM 97).

Solo municipio «Madrid» (capital), no el resto de la provincia/CM.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from .resolvers_builtin import (
    Resolution,
    SectorContext,
    _http_get_json,
    _sql_escape,
    centroid_from_geojson_obj,
    norm_eq,
)


SIGMA_PG_ORDENACION = "https://sigma.madrid.es/hosted/rest/services/PGOUM97/PG_ORDENACION/MapServer"
SIGMA_PG_GESTION = "https://sigma.madrid.es/hosted/rest/services/PGOUM97/PG_GESTION/MapServer"


def is_madrid_ciudad(ctx: SectorContext) -> bool:
    """Capital: municipio normalizado exactamente «madrid»."""
    return norm_eq(ctx.municipio_raw) == "madrid"


def _extract_ambito_codes(sector_raw: str) -> list[str]:
    """Códigos PGOUM (APR.17.03, API.05.04, SUZ II-4, CODAMBGES, etc.)."""
    s = sector_raw.strip()
    if not s:
        return []
    codes: list[str] = []
    patterns = [
        r"\b[A-Z]{2,5}\.\d{1,3}\.\d{1,3}\b",
        r"\b[A-Z]{2,5}\s+[IVXLC\d]+(?:\s*[-–]\s*\d+)?\b",
        r"\b[A-Z]{2,5}[-\s]?\d+[A-Z]?\b",
        r"\bSUZ\s*(?:II|III|IV|I)?\s*[-–]?\s*\d+\b",
        r"\bPAU[-\s]?\w+\b",
        r"\bUZPP\s*\d+\b",
    ]
    seen: set[str] = set()
    for pat in patterns:
        for m in re.finditer(pat, s.upper()):
            c = re.sub(r"\s+", " ", m.group(0).strip())
            if len(c) < 2:
                continue
            k = c.lower()
            if k not in seen:
                seen.add(k)
                codes.append(c)
    return codes[:8]


def _arcgis_query_geojson(
    mapserver_base: str,
    layer_id: int,
    where: str,
    *,
    record_count: int = 25,
) -> dict[str, Any] | None:
    qs = urllib.parse.urlencode(
        {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
            "resultRecordCount": str(record_count),
        }
    )
    url = f"{mapserver_base.rstrip('/')}/{layer_id}/query?{qs}"
    data = _http_get_json(url)
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        return None
    feats = data.get("features") or []
    if not feats:
        return None
    return data


def _merge_feature_collection(feats: list[dict[str, Any]], props: dict[str, Any]) -> dict[str, Any] | None:
    if not feats:
        return None
    if len(feats) == 1:
        f = feats[0]
        if isinstance(f.get("properties"), dict):
            f["properties"].update(props)
        return {"type": "FeatureCollection", "features": [f]}
    geoms = [f.get("geometry") for f in feats if isinstance(f.get("geometry"), dict)]
    polys: list[Any] = []
    for g in geoms:
        if g.get("type") == "Polygon":
            polys.append(g["coordinates"])
        elif g.get("type") == "MultiPolygon":
            polys.extend(g["coordinates"])
    if not polys:
        f0 = feats[0]
        if isinstance(f0.get("properties"), dict):
            f0["properties"].update(props)
        return {"type": "FeatureCollection", "features": [f0]}
    merged_geom: dict[str, Any]
    if len(polys) == 1:
        merged_geom = {"type": "Polygon", "coordinates": polys[0]}
    else:
        merged_geom = {"type": "MultiPolygon", "coordinates": polys}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {**props, "n_features_merged": len(feats)},
                "geometry": merged_geom,
            }
        ],
    }


class MadridAytoPgoumResolver:
    """
    Polígonos PGOUM 97 (SIGMA) para Madrid capital.
    Prueba códigos de ámbito extraídos del texto del sector.
    """

    id: str
    cfg: dict[str, Any]

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.id = str(cfg.get("id") or "madrid_ayto_pgoum")

    def accepts(self, ctx: SectorContext) -> bool:
        bid = (ctx.boletin_source_id or "").strip().lower()
        if bid and bid != "bocm":
            return False
        if not is_madrid_ciudad(ctx):
            return False
        return bool(ctx.sector_raw.strip())

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        codes = _extract_ambito_codes(ctx.sector_raw)
        if not codes:
            return None

        attempts: list[tuple[str, int, str, str]] = [
            (SIGMA_PG_ORDENACION, 3, "CODAMBORD", "ordenacion_rotulacion"),
            (SIGMA_PG_GESTION, 6, "CODAMBGES", "gestion_rotulacion"),
        ]

        sector_fold = ctx.sector_raw.lower()
        for code in codes:
            esc = _sql_escape(code)
            for base, layer_id, field, scope in attempts:
                wheres = [
                    f"{field} = '{esc}'",
                    f"UPPER({field}) = UPPER('{esc}')",
                ]
                if "." not in code and len(code) >= 3:
                    wheres.append(f"UPPER({field}) LIKE UPPER('%{esc}%')")
                for where in wheres:
                    fc = _arcgis_query_geojson(base, layer_id, where)
                    if not fc:
                        continue
                    feats = fc.get("features") or []
                    best = feats[0]
                    best_score = -1.0
                    for f in feats:
                        p = f.get("properties") or {}
                        cod = str(p.get(field) or p.get("CODAMBORD") or p.get("CODAMBGES") or "")
                        score = 0.0
                        if cod.lower() in sector_fold:
                            score += 20
                        if code.lower() in cod.lower():
                            score += 10
                        if score > best_score:
                            best_score = score
                            best = f
                    merged = _merge_feature_collection(
                        [best] if len(feats) == 1 else feats[:5],
                        {
                            "geometry_scope": scope,
                            "matched_code": code,
                            "field": field,
                        },
                    )
                    if not merged:
                        continue
                    c = centroid_from_geojson_obj(merged)
                    if not c:
                        continue
                    lon, lat = c
                    return Resolution(
                        geometry_geojson=json.dumps(merged, ensure_ascii=False),
                        centroid_lon=lon,
                        centroid_lat=lat,
                        resolver_id=self.id,
                        detail={
                            "geometry_scope": scope,
                            "matched_code": code,
                            "field": field,
                            "layer_id": layer_id,
                            "feature_count": len(feats),
                        },
                    )
        return None
