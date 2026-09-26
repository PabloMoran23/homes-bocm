from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://aspe.es"
SEDE_BASE = "https://sede.aspe.es"
MUNICIPIO = "Aspe"
ID_PREFIX = "aspe"
COD_INE_MUN = "03009"

CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
NORMATIVA_URL = f"{WEB_BASE}/normativa-urbanistica/"
TABLON_ELECTRONICO_URL = f"{WEB_BASE}/tablon-de-anuncios-electronico/"
TABLON_URL = f"{WEB_BASE}/tablon-de-anuncios/"

SITEMAP_URLS = [
    f"{WEB_BASE}/wp-sitemap-posts-anuncio-electronico-1.xml",
    f"{WEB_BASE}/wp-sitemap-posts-anuncio-electronico-2.xml",
    f"{WEB_BASE}/wp-sitemap-posts-anuncio-tablon-1.xml",
]

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = [
    0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500,
    7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500,
    13000, 13500,
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"licencia ambiental|licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pai|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de integraci[oó]n)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"unidad de ejecuci|urbanizaci[oó]n|homologaci[oó]n|integraci[oó]n paisag|"
    r"participaci[oó]n p[uú]blica|ejecuci[oó]n subsidiaria|demolici[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(padron municipal|inclusion indebida|baja por inclusion|baja-padron|"
    r"proceso selectivo|convocatoria.*empleo|modificaci[oó]n.*presupuest|presupuest|"
    r"declaraci[oó]n de actividades y bienes|sello electr[oó]nico|delegaci[oó]n.*alcaldia|"
    r"miembros de la corporaci[oó]n|premio de|concurso de|elecciones|"
    r"cuentas correspondientes|mancomunidad|agencia tributaria|subvenci[oó]n|"
    r"nombramiento|bolsa de|cuestionario tipo test|plaza de|limpiador|auxiliar administr)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+)")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*([\d/_-]+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _title_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    title = unquote(slug.replace("-", " "))
    return re.sub(r"\s+", " ", title).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_lastmod(value: str) -> str | None:
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _fecha_from_blob(text: str) -> str | None:
    for parser in (_parse_fecha_dmy, _parse_fecha_iso):
        d = parser(text)
        if d:
            return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_expediente(expediente: str) -> str | None:
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 8:
        try:
            y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
            if 1980 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(expediente or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "reparcel" in n:
        return "reparcelación"
    if "urbanizaci" in n:
        return "urbanización"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "licencia ambiental" in n:
        return "licencia ambiental"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "integraci" in n and "paisag" in n:
        return "integración paisajística"
    return "urbanismo"


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


class AspeAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress The7 (aspe.es tablón CPT) + sede STA (catálogo) + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.sitemap_urls = [str(u) for u in (self.config.get("sitemap_urls") or SITEMAP_URLS)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._icv_zones_cache: list[dict[str, Any]] | None = None
        self._sitemap_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aspe/1.0")},
        )
        ctx = self._ssl_ctx if "sede.aspe.es" in url else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aspe/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_sitemap_entries(self) -> list[dict[str, Any]]:
        if self._sitemap_cache is not None:
            return self._sitemap_cache

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sm_url in self.sitemap_urls:
            try:
                xml_text = self._fetch(sm_url, timeout=90)
                root = ET.fromstring(xml_text)
            except (urllib.error.URLError, ET.ParseError):
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_el in root.findall("sm:url", ns):
                loc_el = url_el.find("sm:loc", ns)
                if loc_el is None or not loc_el.text:
                    continue
                url = loc_el.text.strip()
                if url in seen:
                    continue
                seen.add(url)
                lastmod_el = url_el.find("sm:lastmod", ns)
                lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else ""
                titulo = _title_from_url(url)
                rows.append(
                    {
                        "url": url,
                        "titulo": titulo,
                        "fecha": _fecha_from_lastmod(lastmod) or _fecha_from_blob(titulo),
                        "origen": "wp_sitemap",
                    }
                )
        self._sitemap_cache = rows
        return rows

    def _collect_normativa_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normativa_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PDF.findall(html):
            pdf = href if href.startswith("http") else f"{self.web_base}{href}"
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unquote(Path(pdf).name)
            if not any(k in name.lower() for k in ("urban", "termino", "pgou", "plan", "clasific", "zonif")):
                if "/urbanismo/" not in pdf.lower() and "REFUNDIDO" not in name.upper():
                    continue
            rows.append(
                {
                    "titulo": name.replace(".pdf", "").replace("-", " ")[:500],
                    "fecha": _fecha_from_blob(name),
                    "url": self.normativa_url,
                    "pdf_url": pdf,
                    "origen": "normativa_pgou",
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            codes = {str(k.get("code") or "") for k in keywords}
            family = str(item.get("nameFamily") or "")
            if not (codes & {"URB", "URB-LIC", "URB-ACT"} or family == "Urbanismo"):
                continue
            if not RE_LICENCIA.search(str(item.get("name") or "")) and "URB-" not in str(item.get("code") or ""):
                continue
            name = str(item.get("name") or "").strip()
            dboid = str(item.get("dboid") or "")
            code = str(item.get("code") or dboid)
            if not name or not dboid:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": _parse_fecha_dmy(str(item.get("from") or "")),
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": self._tramite_url(dboid),
                    "source": "ayuntamiento",
                    "nota": "Trámite catálogo sede STA; no concesión publicada",
                    "tramite_code": code,
                    "origen": "catalogo_sta",
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
                data = self._fetch_json(url)
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

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        sector_m = RE_SECTOR.search(titulo or "")
        sector = sector_m.group(1).upper() if sector_m else None
        best: tuple[float, dict[str, Any]] | None = None

        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif sector and f"SECTOR {sector}" in den:
                score = 80.0
            elif sector and f"SECTOR{sector}" in den.replace(" ", ""):
                score = 75.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                if hits:
                    score = 20.0 + hits * 10.0
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, zone)
        return best[1] if best else None

    def _zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        geom = zone.get("geom_geojson")
        if not isinstance(geom, dict):
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": zone.get("geometry_source_url") or self.icv_wfs_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom_fields = self._zone_geometry(zone)
        if geom_fields:
            rec.update(geom_fields)
            cen = geometry_centroid(geom_fields["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        visor_gva = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        rows: list[dict[str, Any]] = []
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            if titulo.lower().strip() == "plan general" and zone.get("expediente") == "00000000":
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_gva,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom_fields = self._zone_geometry(zone)
            if geom_fields:
                rec.update(geom_fields)
                cen = geometry_centroid(geom_fields["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _sitemap_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row['url']}"
        if RE_NOISE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        expte_m = RE_EXPTE.search(blob)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1)
        self._enrich_geometry(rec)
        return rec

    def _sitemap_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row['url']}"
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and "licencia" not in blob.lower():
            return None
        expte_m = RE_EXPTE.search(blob)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1)
        self._enrich_geometry(rec)
        return rec

    def _normativa_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("pdf_url") or row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": "PGOU",
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_catalog_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for entry in self._collect_sitemap_entries():
            rec = self._sitemap_to_licencia(entry)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        info_rows = [
            {
                "id": _stable_id("lic", TABLON_ELECTRONICO_URL),
                "fecha_concesion": None,
                "tipo": "tablón anuncios electrónico",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios electrónico — Aspe",
                "url": TABLON_ELECTRONICO_URL,
                "source": "ayuntamiento",
                "nota": "CPT WordPress anuncio-electronico; edictos urbanísticos",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo trámites sede STA — licencias URB-*",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Trámites URB-1..25 en sede.aspe.es; sin listado de concesiones",
                "origen": "catalogo_sta",
            },
        ]
        for rec in info_rows:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalogo_sta": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
            "tablon": sum(1 for r in rows if r.get("origen") == "wp_sitemap"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in self._collect_sitemap_entries():
            rec = self._sitemap_to_proyecto(entry)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for doc in self._collect_normativa_pdfs():
            rec = self._normativa_to_proyecto(doc)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_icv_proyectos():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        info = {
            "id": _stable_id("proy", self.normativa_url),
            "municipio": MUNICIPIO,
            "titulo": "Normativa urbanística — PGOU Aspe",
            "fecha": None,
            "tipo": "normativa",
            "url": self.normativa_url,
            "source": "ayuntamiento",
            "origen": "web_normativa",
        }
        if info["id"] not in seen:
            rows.append(info)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_sitemap": sum(1 for r in rows if r.get("origen") == "wp_sitemap"),
            "normativa_pgou": sum(1 for r in rows if r.get("origen") == "normativa_pgou"),
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
