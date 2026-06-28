from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "poc-bocm-municipio-geometry/1.0"


def _http_get_json(url: str, timeout: float = 45.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _format_where(template: str, rec: dict[str, Any]) -> str:
    ctx = {
        "expediente": str(rec.get("expediente") or rec.get("codigo") or ""),
        "titulo": str(rec.get("titulo") or rec.get("denominacion") or ""),
        "id": str(rec.get("id") or ""),
    }
    out = template
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", val.replace("'", "''"))
    return out


def query_mapserver_geojson(cfg: dict[str, Any], rec: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    base = str(cfg.get("mapserver_base") or "").rstrip("/")
    layer_id = int(cfg.get("layer_id", 0))
    where = _format_where(str(cfg.get("where_template") or "1=1"), rec)
    qs = urllib.parse.urlencode(
        {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson",
            "outSR": "4326",
            "resultRecordCount": str(int(cfg.get("result_record_count") or 5)),
        }
    )
    url = f"{base}/{layer_id}/query?{qs}"
    meta: dict[str, Any] = {"source": "portal_visor_arcgis", "query_url": url[:500]}
    try:
        data = _http_get_json(url)
    except Exception as e:
        meta["reason"] = str(e)
        return None, meta

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        meta["reason"] = "not_feature_collection"
        return None, meta

    feats = data.get("features") or []
    if not feats:
        meta["reason"] = "empty"
        return None, meta

    geom = feats[0].get("geometry")
    if not isinstance(geom, dict):
        meta["reason"] = "no_geometry"
        return None, meta

    meta["feature_count"] = len(feats)
    return geom, meta
