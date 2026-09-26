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

WEB_BASE = "https://www.lolleria.org"
SEDE_BASE = "https://lolleria.sedelectronica.es"
URBANISMO_URL = f"{WEB_BASE}/es/pagina/urbanismo"
TRANSPARENCIA_URL = f"{WEB_BASE}/es/pagina/transparencia"
MUNICIPIO = "L'Olleria"
ID_PREFIX = "l-olleria"
COD_INE_MUN = "46189"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500, 14000, 14500, 15000, 15500, 16000, 16500, 17000, 17500, 18000, 18500, 19000, 19500]

LICENCIA_OBRA_C = f"{WEB_BASE}/sites/www.lolleria.org/files/sol%C2%B7licitud%20llic%C3%A8ncia%20obres_c.pdf"
LICENCIA_OBRA_V = f"{WEB_BASE}/sites/www.lolleria.org/files/sol%C2%B7licitud%20llic%C3%A8ncia%20obres_v.pdf"

RE_TRANSP_URBAN = re.compile(
    r"(?i)(urban|norm|pla[\s._-]*general|pla[\s._-]*parcial|pgou|galol|teularet|"
    r"licen.*urban|014lic|edicte.*(?:plan|pgou|urban|pai|modif)|conveni.*urban|"
    r"dossier.*urban|reparcel|modif.*puntual|normatiu|propuesta.*urban|ficha.*urban)",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https://www\.lolleria\.org)?/sites/www\.lolleria\.org/files/[^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _fecha_from_filename(name: str) -> str | None:
    years = [int(x.group(1)) for x in RE_YEAR.finditer(name or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(name: str) -> str:
    n = (name or "").lower()
    if "pla general" in n or "pgou" in n or "plan general" in n:
        return "PGOU"
    if "pla parcial" in n or "plan parcial" in n or "galol" in n or "teularet" in n:
        return "plan parcial"
    if "modif" in n and ("puntual" in n or "pgou" in n or "plan" in n):
        return "modificación planeamiento"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "normas subsidiarias" in n or "normes urban" in n or "normatiu" in n:
        return "normativa urbanística"
    if "conveni" in n and "urban" in n:
        return "convenio urbanístico"
    if "reparcel" in n:
        return "reparcelación"
    if "informacio publica" in n or "edicte" in n:
        return "información pública"
    if "licen" in n:
        return "licencias urbanísticas"
    if "dossier" in n and "urban" in n:
        return "propuesta urbanística"
    return "planeamiento"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry") if "geometry" in f else f.get("geom_geojson")
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


class LOlleriaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portales (lolleria.org) + sede espublico inactiva + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.transparencia_url = str(self.config.get("transparencia_url") or TRANSPARENCIA_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_zones_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-l-olleria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-l-olleria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_web(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.web_base}{href if href.startswith('/') else '/' + href}"

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparencia_url, timeout=90)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_web(m.group(1))
            if href in seen:
                continue
            fname = urllib.parse.unquote(href.rsplit("/", 1)[-1])
            if not RE_TRANSP_URBAN.search(fname):
                continue
            seen.add(href)
            titulo = re.sub(r"^\d+\.\s*", "", fname.replace(".pdf", "").replace("_", " ").replace("-", " "))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": href,
                    "fecha": _fecha_from_filename(fname),
                    "filename": fname,
                }
            )
        return rows

    def _collect_icv_zones(self) -> list[dict[str, Any]]:
        if self._icv_zones_cache is not None:
            return self._icv_zones_cache

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for start in self.icv_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.icv_type_name,
                    "outputFormat": "application/json; subtype=geojson",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.icv_wfs_url}?{params}"
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            batch = data.get("features") or []
            if not batch:
                break
            for feat in batch:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                    continue
                den = str(props.get("denominaci") or "").strip()
                exp = str(props.get("expediente") or "").strip()
                if not den:
                    continue
                grouped.setdefault((den, exp), []).append(feat)

        zones: list[dict[str, Any]] = []
        for (den, exp), feats in grouped.items():
            merged = _merge_geometries(feats)
            zones.append(
                {
                    "denominaci": den,
                    "expediente": exp,
                    "tipo": _proyecto_tipo(den),
                    "geom_geojson": merged,
                    "geometry_source_url": (
                        f"{self.icv_wfs_url}?service=WFS&request=GetFeature&"
                        f"typeName={self.icv_type_name}&cod_ine_mun={self.cod_ine_mun}"
                    ),
                }
            )

        self._icv_zones_cache = zones
        return zones

    def _zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        geom = zone.get("geom_geojson")
        if not geom:
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": zone.get("geometry_source_url") or self.icv_wfs_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        best: tuple[float, dict[str, Any]] | None = None
        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 12.0
            if "NORMAS SUBSIDIARIAS" in norm and "NORMAS SUBSIDIARIAS" in den:
                score += 30.0
            if "HOMOLOGACION" in norm and "HOMOLOGACION" in den:
                score += 30.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)
        if best and best[0] >= 24:
            return best[1]
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._zone_geometry(zone)
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitud licencia de obra — web municipal",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF (comercio y vivienda) en sección Urbanismo",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", LICENCIA_OBRA_C),
                "fecha_concesion": None,
                "tipo": "licencia de obra (comercio)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sol·licitud llicència obres — comercio",
                "url": LICENCIA_OBRA_C,
                "source": "ayuntamiento",
                "origen": "web_formulario",
            },
            {
                "id": _stable_id("lic", LICENCIA_OBRA_V),
                "fecha_concesion": None,
                "tipo": "licencia de obra (vivienda)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sol·licitud llicència obres — vivienda",
                "url": LICENCIA_OBRA_V,
                "source": "ayuntamiento",
                "origen": "web_formulario",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica (inactiva)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — tablón de anuncios (inactiva)",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "lolleria.sedelectronica.es temporalmente inactiva; sin tablón público",
                "origen": "sede_tablon",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        visor_gva = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        return [
            {
                "id": _stable_id("proy", self.transparencia_url),
                "municipio": MUNICIPIO,
                "titulo": "Portal de transparencia — documentación urbanística",
                "fecha": None,
                "tipo": "transparencia",
                "url": self.transparencia_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("proy", self.urbanismo_url),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo — Ayuntamiento de L'Olleria",
                "fecha": None,
                "tipo": "urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web",
            },
            {
                "id": _stable_id("proy", visor_gva),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": visor_gva,
                "source": "ayuntamiento",
                "origen": "datos_abiertos",
            },
        ]

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_url = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            if zone.get("expediente"):
                titulo = f"{titulo} (exp. {zone['expediente']})"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{zone['denominaci']}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_filename(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_transparencia_pdfs():
            rec: dict[str, Any] = {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": item.get("fecha"),
                "tipo": _proyecto_tipo(item.get("filename") or item["titulo"]),
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "transparencia_pdf",
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": len(rows),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for rec in self._collect_icv_proyectos():
            add(rec)
        for rec in self._collect_transparencia_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_pdf"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
