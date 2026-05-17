from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class SectorContext:
    municipio_raw: str
    sector_raw: str
    municipio_norm: str
    sector_norm: str
    municipio_provincia_raw: str | None
    boletin_source_id: str | None
    stable_key: str


@dataclass
class Resolution:
    geometry_geojson: str
    centroid_lon: float
    centroid_lat: float
    resolver_id: str
    detail: dict[str, Any]


class SectorResolver(Protocol):
    id: str

    def accepts(self, ctx: SectorContext) -> bool:
        ...

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        ...


def _iter_coords_geom(g: dict[str, Any]) -> list[tuple[float, float]]:
    """Recorre coordenadas GeoJSON (Polygon / MultiPolygon)."""
    out: list[tuple[float, float]] = []
    t = g.get("type")
    coords = g.get("coordinates")
    if t == "Point" and isinstance(coords, list) and len(coords) >= 2:
        out.append((float(coords[0]), float(coords[1])))
    elif t == "Polygon" and isinstance(coords, list):
        for ring in coords:
            if isinstance(ring, list):
                for pt in ring:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        out.append((float(pt[0]), float(pt[1])))
    elif t == "MultiPolygon" and isinstance(coords, list):
        for poly in coords:
            if not isinstance(poly, list):
                continue
            for ring in poly:
                if isinstance(ring, list):
                    for pt in ring:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            out.append((float(pt[0]), float(pt[1])))
    return out


def centroid_from_geojson_obj(obj: dict[str, Any]) -> tuple[float, float] | None:
    """Centro del bounding box de la primera geometría útil (lon, lat en EPSG:4326)."""
    geom: dict[str, Any] | None = None
    if obj.get("type") == "FeatureCollection":
        feats = obj.get("features") or []
        for f in feats:
            if isinstance(f, dict) and isinstance(f.get("geometry"), dict):
                geom = f["geometry"]
                break
    elif obj.get("type") == "Feature" and isinstance(obj.get("geometry"), dict):
        geom = obj["geometry"]
    elif "coordinates" in obj and "type" in obj:
        geom = obj
    if not geom:
        return None
    pts = _iter_coords_geom(geom)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _http_get_json(url: str, timeout: float = 60.0, user_agent: str | None = None) -> Any:
    ua = user_agent or "poc-bocm-sector-geometry/0.1"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def norm_eq(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def _format_where(tmpl: str, ctx: SectorContext) -> str:
    return (
        tmpl.replace("{sector_sql}", _sql_escape(ctx.sector_raw))
        .replace("{municipio_sql}", _sql_escape(ctx.municipio_raw))
        .replace("{sector_raw}", ctx.sector_raw)
        .replace("{sector_norm}", ctx.sector_norm)
        .replace("{municipio_raw}", ctx.municipio_raw)
        .replace("{municipio_norm}", ctx.municipio_norm)
    )


def accepts_common_filters(cfg: dict[str, Any], ctx: SectorContext) -> bool:
    """
    Filtros opcionales en JSON de resolver:
    - municipio_norm_equals: solo ese municipio (normalizado).
    - boletin_source_id_equals: solo esa fuente (p.ej. bocm).
    - boletin_source_id_in: lista de fuentes permitidas.
    - boletin_source_id_prefix: la fuente debe empezar por este prefijo.
    """
    muni_f = cfg.get("municipio_norm_equals")
    if muni_f and ctx.municipio_norm != norm_eq(str(muni_f)):
        return False
    want = cfg.get("boletin_source_id_equals")
    if want and norm_eq(ctx.boletin_source_id) != norm_eq(str(want)):
        return False
    in_list = cfg.get("boletin_source_id_in")
    if isinstance(in_list, list) and in_list:
        cur = norm_eq(ctx.boletin_source_id)
        allowed = {norm_eq(str(x)) for x in in_list}
        if cur not in allowed:
            return False
    prefix = cfg.get("boletin_source_id_prefix")
    if prefix:
        cur = norm_eq(ctx.boletin_source_id) or ""
        p = str(prefix).strip().lower()
        if not cur.startswith(p):
            return False
    return True


class ArcGISRestQueryResolver:
    """
    Consulta un MapServer de ArcGIS (`.../MapServer`) en modo geojson.

    Config (dict):
      id: str
      mapserver_base: str
      layer_id: int
      boletin_source_id_equals: str | null
      municipio_norm_equals: str | null
      where_template: str
    """

    id: str

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.id = str(cfg.get("id") or "arcgis_rest")

    def accepts(self, ctx: SectorContext) -> bool:
        return accepts_common_filters(self.cfg, ctx)

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        base = str(self.cfg.get("mapserver_base") or "").rstrip("/")
        layer_id = int(self.cfg["layer_id"])
        tmpl = str(self.cfg.get("where_template") or "1=1")
        where = _format_where(tmpl, ctx)
        qs = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            }
        )
        url = f"{base}/{layer_id}/query?{qs}"
        data = _http_get_json(url)
        if data.get("type") != "FeatureCollection":
            return None
        feats = data.get("features") or []
        if len(feats) != 1:
            return None
        c = centroid_from_geojson_obj(data)
        if not c:
            return None
        lon, lat = c
        return Resolution(
            geometry_geojson=json.dumps(data, ensure_ascii=False),
            centroid_lon=lon,
            centroid_lat=lat,
            resolver_id=self.id,
            detail={"query_url": url[:500], "feature_count": len(feats)},
        )


def _normalize_wfs_geojson(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        return data
    if isinstance(data, dict) and data.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    if isinstance(data, list):
        return {"type": "FeatureCollection", "features": data}
    return None


class WfsGetFeatureResolver:
    """
    WFS GetFeature (p. ej. GeoServer). Requiere outputFormat que devuelva GeoJSON
    (application/json, geojson, etc. según el servidor).

    Config:
      id, wfs_url (base con ? opcional), type_name (capa workspace:capa),
      version (default 2.0.0), output_format, srs_name (EPSG:4326),
      cql_filter_template (mismas plantillas que where_template en ArcGIS),
      count (máx. features a traer antes de exigir unicidad; default 5).
    """

    id: str

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.id = str(cfg.get("id") or "wfs_getfeature")

    def accepts(self, ctx: SectorContext) -> bool:
        return accepts_common_filters(self.cfg, ctx)

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        wfs_url = str(self.cfg["wfs_url"]).split("?")[0].rstrip("/")
        type_name = str(self.cfg["type_name"])
        version = str(self.cfg.get("version", "2.0.0"))
        out_fmt = str(self.cfg.get("output_format") or "application/json")
        params: dict[str, str] = {
            "service": "WFS",
            "request": "GetFeature",
            "version": version,
            "typeName": type_name,
            "outputFormat": out_fmt,
            "srsName": str(self.cfg.get("srs_name", "EPSG:4326")),
            "count": str(int(self.cfg.get("count", 5))),
        }
        cql_tmpl = self.cfg.get("cql_filter_template") or self.cfg.get("where_template")
        if cql_tmpl:
            cql_val = _format_where(str(cql_tmpl), ctx)
            param_key = str(self.cfg.get("cql_filter_param", "CQL_FILTER"))
            params[param_key] = cql_val
        url = wfs_url + "?" + urllib.parse.urlencode(params)
        data = _http_get_json(url)
        fc = _normalize_wfs_geojson(data)
        if not fc:
            return None
        feats = fc.get("features") or []
        if len(feats) != 1:
            return None
        c = centroid_from_geojson_obj(fc)
        if not c:
            return None
        lon, lat = c
        return Resolution(
            geometry_geojson=json.dumps(fc, ensure_ascii=False),
            centroid_lon=lon,
            centroid_lat=lat,
            resolver_id=self.id,
            detail={"query_url": url[:800], "feature_count": len(feats), "geometry_scope": "wfs_layer_match"},
        )


class NominatimMunicipioResolver:
    """
    Geocodificación aproximada del municipio (punto). No es la delimitación del sector
    de planeamiento; sirve como fallback monitorizable hasta conectar WFS/ArcGIS reales.
    """

    id: str

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.id = str(cfg.get("id") or "nominatim_municipio")
        self._last_query_ts = 0.0

    def accepts(self, ctx: SectorContext) -> bool:
        if not ctx.municipio_raw.strip():
            return False
        return accepts_common_filters(self.cfg, ctx)

    def _pace(self) -> None:
        min_interval = float(self.cfg.get("min_interval_s", 1.1))
        now = time.monotonic()
        wait = self._last_query_ts + min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last_query_ts = time.monotonic()

    def resolve(self, ctx: SectorContext) -> Resolution | None:
        self._pace()
        prov = ""
        if ctx.municipio_provincia_raw:
            parts = [p.strip() for p in ctx.municipio_provincia_raw.split(",") if p.strip()]
            if len(parts) >= 2:
                prov = parts[-1]
        q_parts = [ctx.municipio_raw, prov, "España"] if prov else [ctx.municipio_raw, "España"]
        q = ", ".join(q_parts)
        contact = os.getenv(
            "SECTOR_NOMINATIM_CONTACT",
            "poc-bocm-sector-geometry (no-reply; +https://example.invalid)",
        )
        ua = f"{contact} poc-bocm/0.1"
        params = urllib.parse.urlencode(
            {"q": q, "format": "jsonv2", "limit": 1, "addressdetails": "0"}
        )
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        rows = _http_get_json(url, timeout=30.0, user_agent=ua)
        if not isinstance(rows, list) or not rows:
            return None
        hit0 = rows[0]
        try:
            lat = float(hit0["lat"])
            lon = float(hit0["lon"])
        except (KeyError, TypeError, ValueError):
            return None
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "scope": "municipio_centroid_fallback",
                        "display_name": hit0.get("display_name"),
                        "osm_type": hit0.get("osm_type"),
                        "osm_id": hit0.get("osm_id"),
                        "sector_context": ctx.sector_raw,
                    },
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                }
            ],
        }
        return Resolution(
            geometry_geojson=json.dumps(fc, ensure_ascii=False),
            centroid_lon=lon,
            centroid_lat=lat,
            resolver_id=self.id,
            detail={
                "geometry_scope": "municipio_centroid_fallback",
                "nominatim_query": q,
                "display_name": hit0.get("display_name"),
                "warning": "No es el polígono del sector de planeamiento; solo ancla geográfica municipal.",
            },
        )


def load_resolvers_from_json(path: str | Path) -> list[SectorResolver]:
    p = Path(path)
    if not p.is_file():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    items = raw.get("resolvers") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    out: list[SectorResolver] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type") or "").lower()
        if t in ("arcgis_rest_query", "arcgis", "arcgis_rest"):
            out.append(ArcGISRestQueryResolver(it))
        elif t in ("wfs_getfeature", "wfs"):
            out.append(WfsGetFeatureResolver(it))
        elif t in ("nominatim_municipio", "nominatim", "nominatim_municipio_centroid"):
            out.append(NominatimMunicipioResolver(it))
        elif t in ("madrid_sitcm_vpla_ambito", "madrid_sitcm_ambito"):
            from .resolvers_madrid import MadridSitcmAmbitoResolver

            out.append(MadridSitcmAmbitoResolver(it))
        elif t in ("madrid_ayto_pgoum", "madrid_ayto_pgoum_ambito"):
            from .resolvers_madrid_ayto import MadridAytoPgoumResolver

            out.append(MadridAytoPgoumResolver(it))
    return out


def try_resolve_chain(resolvers: list[SectorResolver], ctx: SectorContext) -> tuple[Resolution | None, str | None]:
    """
    Devuelve (resolución, motivo_si_falla).
    motivo: 'no_resolver_accepted' si ningún resolver aceptó el contexto.
    """
    any_accepted = False
    for r in resolvers:
        if not r.accepts(ctx):
            continue
        any_accepted = True
        try:
            hit = r.resolve(ctx)
        except Exception:
            continue
        if hit:
            return hit, None
    if not any_accepted:
        return None, "no_resolver_accepted"
    return None, None
