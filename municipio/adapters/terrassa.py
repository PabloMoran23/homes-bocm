from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://aoberta.terrassa.cat"
MUNICIPIO = "Terrassa"
ID_PREFIX = "terrassa"

VISOR_POUM = "https://emap.terrassa.cat/mapGIS/?modul=POUM"
ARCGIS_MS = (
    "http://emap.terrassa.cat/arcgis/rest/services/Territori/iurb_terrassa/MapServer"
)
SECTORS_LAYER_ID = 4

URBANISMO_TRAMITS_URL = f"{SEDE_BASE}/oficines/infoEntitatTramits.jsp?id=1899"
CARPETA_CIUDADANA = (
    "https://ariadnaseu.terrassa.cat/sta/CarpetaPublic/doEvent"
    "?APP_CODE=STA&PAGE_CODE=FRONTAL_OVC&lang=ES"
)

RE_TRAMITE_LINK = re.compile(
    r'href="(/tramits/fitxa\.jsp\?id=\d+)"[^>]*>\s*([^<]+)',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|primera utilitzaci[oó]|primera ocupaci[oó]|"
    r"obres? (?:major|menor)|enderroc|parcel·laci[oó])",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(attrs: dict[str, Any]) -> str:
    blob = " ".join(
        str(attrs.get(k) or "")
        for k in ("tipop", "ntinstr", "ntlnstr", "denominacio", "estat", "Classificacio")
    ).lower()
    if "pla especial" in blob or attrs.get("tipop") == "PE":
        return "plan especial"
    if "pla parcial" in blob or attrs.get("tipop") == "PP":
        return "plan parcial"
    if "estudi" in blob and "detall" in blob:
        return "estudio de detalle"
    if "unitat" in blob or "ue" in blob:
        return "unidad de ejecución"
    if "sector" in blob or attrs.get("tipop") == "ST":
        return "sector planeamiento"
    if "poum" in blob or "pla general" in blob or attrs.get("tipop") == "PG":
        return "POUM"
    return "planeamiento"


def _merge_geojson(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
        gtype = g.get("type")
        coords = g.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _esri_geom_to_geojson(geom: dict[str, Any] | None) -> dict[str, Any] | None:
    if not geom:
        return None
    rings_raw = geom.get("rings")
    if not isinstance(rings_raw, list):
        return None
    rings: list[list[list[float]]] = []
    for ring in rings_raw:
        if not isinstance(ring, list):
            continue
        coords = [[float(p[0]), float(p[1])] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if len(coords) >= 4:
            rings.append(coords)
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}


class TerrassaAyuntamientoAdapter(AyuntamientoAdapter):
    """POUM ArcGIS (emap) + sede aoberta (trámites licencias; sin tablón histórico público)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        geom_cfg = self.config.get("geometry") or {}
        self.arcgis_ms = str(geom_cfg.get("base_url") or ARCGIS_MS).rstrip("/")
        self.sectors_layer_id = int(geom_cfg.get("layer_id", SECTORS_LAYER_ID))
        self.visor_url = str(self.config.get("visor_url") or VISOR_POUM)
        self.tramits_url = str(self.config.get("tramits_url") or URBANISMO_TRAMITS_URL)

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-terrassa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-terrassa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _query_arcgis(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.arcgis_ms}/{self.sectors_layer_id}/query?" + urllib.parse.urlencode(params)
        return self._fetch_json(url)

    def _collect_sector_attrs(self) -> list[dict[str, Any]]:
        out_fields = (
            "OBJECTID,idpoli,denominacio,sexpe,urlseut,urlgenca,estat,tipop,ntinstr,"
            "Data_publicacio,lastdate,ambitsit,Classificacio"
        )
        offset = 0
        attrs_list: list[dict[str, Any]] = []
        while True:
            data = self._query_arcgis(
                {
                    "where": "denominacio IS NOT NULL AND denominacio <> ''",
                    "outFields": out_fields,
                    "returnGeometry": "false",
                    "f": "json",
                    "resultOffset": str(offset),
                    "resultRecordCount": "1000",
                }
            )
            batch = data.get("features") or []
            if not batch:
                break
            for feat in batch:
                attrs = feat.get("attributes") or {}
                if attrs.get("denominacio"):
                    attrs_list.append(attrs)
            if len(batch) < 1000:
                break
            offset += 1000
        return attrs_list

    def _fetch_geometries_by_oid(self, object_ids: list[int]) -> dict[int, dict[str, Any]]:
        geoms: dict[int, dict[str, Any]] = {}
        chunk_size = 20
        for i in range(0, len(object_ids), chunk_size):
            chunk = object_ids[i : i + chunk_size]
            try:
                data = self._query_arcgis(
                    {
                        "objectIds": ",".join(str(x) for x in chunk),
                        "outFields": "OBJECTID",
                        "returnGeometry": "true",
                        "f": "json",
                        "outSR": "4326",
                    }
                )
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                continue
            for feat in data.get("features") or []:
                attrs = feat.get("attributes") or {}
                oid = attrs.get("OBJECTID")
                if oid is None:
                    continue
                geom = _esri_geom_to_geojson(feat.get("geometry"))
                if geom:
                    geoms[int(oid)] = geom
        return geoms

    def _collect_sector_proyectos(self) -> list[dict[str, Any]]:
        attrs_list = self._collect_sector_attrs()
        oids = [int(a["OBJECTID"]) for a in attrs_list if a.get("OBJECTID") is not None]
        geom_by_oid = self._fetch_geometries_by_oid(oids)

        grouped: dict[str, list[dict[str, Any]]] = {}
        geom_parts: dict[str, list[dict[str, Any]]] = {}
        for attrs in attrs_list:
            denom = _strip_html(str(attrs.get("denominacio") or ""))
            idpoli = str(attrs.get("idpoli") or "").strip()
            sexpe = str(attrs.get("sexpe") or "").strip()
            key = idpoli or sexpe or denom
            grouped.setdefault(key, []).append(attrs)
            oid = int(attrs["OBJECTID"]) if attrs.get("OBJECTID") is not None else None
            g = geom_by_oid.get(oid) if oid is not None else None
            if g:
                geom_parts.setdefault(key, []).append(g)

        rows: list[dict[str, Any]] = []
        for key, group in grouped.items():
            attrs = group[0]
            denom = _strip_html(str(attrs.get("denominacio") or ""))
            idpoli = str(attrs.get("idpoli") or "").strip()
            sexpe = str(attrs.get("sexpe") or "").strip()
            fecha = _parse_fecha_dmy(str(attrs.get("Data_publicacio") or "")) or _parse_fecha_dmy(
                str(attrs.get("lastdate") or "")
            )
            url_portal = (
                str(attrs.get("urlseut") or "").strip()
                or str(attrs.get("urlgenca") or "").strip()
                or self.visor_url
            )
            where = (
                f"idpoli='{idpoli.replace(chr(39), chr(39)+chr(39))}'"
                if idpoli
                else f"sexpe='{sexpe.replace(chr(39), chr(39)+chr(39))}'"
                if sexpe
                else f"denominacio='{denom.replace(chr(39), chr(39)+chr(39))}'"
            )
            query_url = (
                f"{self.arcgis_ms}/{self.sectors_layer_id}/query?"
                + urllib.parse.urlencode(
                    {
                        "where": where,
                        "outFields": "*",
                        "returnGeometry": "true",
                        "f": "json",
                        "outSR": "4326",
                    }
                )
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": denom,
                "fecha": fecha,
                "tipo": _proyecto_tipo(attrs),
                "url": url_portal,
                "source": "ayuntamiento",
                "origen": "arcgis_sectors_poum",
                "idpoli": idpoli or None,
                "expediente": sexpe or None,
                "estat": attrs.get("estat"),
                "feature_parts": len(group),
            }
            merged = _merge_geojson(geom_parts.get(key) or [])
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_source"] = "portal_visor_arcgis"
                rec["geometry_source_url"] = query_url
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(merged)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)

        return rows

    def _collect_info_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.visor_url),
                "municipio": MUNICIPIO,
                "titulo": "e-map Terrassa — visor POUM (planejament urbanístic)",
                "fecha": None,
                "tipo": "visor planeamiento",
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "visor_info",
            },
        ]

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramits_url)
        except urllib.error.URLError:
            return self._collect_licencia_fallback()

        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []
        for m in RE_TRAMITE_LINK.finditer(html):
            href, title = m.group(1), _strip_html(m.group(2))
            if not RE_LICENCIA.search(title):
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)
            url = urllib.parse.urljoin(f"{SEDE_BASE}/", href)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": title[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_tramite",
                }
            )
        if not rows:
            return self._collect_licencia_fallback()
        return rows

    def _collect_licencia_fallback(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramits_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo — licencias y comunicaciones",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Serveis d'Urbanisme — catálogo de trámites",
                "url": self.tramits_url,
                "source": "ayuntamiento",
                "origen": "sede_tramite",
                "nota": "Sin listado histórico público de licencias concedidas",
            },
            {
                "id": _stable_id("lic", CARPETA_CIUDADANA),
                "fecha_concesion": None,
                "tipo": "consulta estado expediente (interés legítimo)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Carpeta ciudadana — consulta expedientes",
                "url": CARPETA_CIUDADANA,
                "source": "ayuntamiento",
                "origen": "carpeta_ciudadana",
            },
        ]

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramites": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": stats["rows"], "added": max(0, stats["rows"] - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_sector_proyectos():
            add(rec)
        for rec in self._collect_info_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "arcgis_sectors": sum(1 for r in rows if r.get("origen") == "arcgis_sectors_poum"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": stats["rows"],
            "added": max(0, stats["rows"] - before),
            "status": "ok",
            **stats,
        }
