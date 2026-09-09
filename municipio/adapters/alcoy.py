from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.alcoi.org"
SEDE_BASE = "https://sedeelectronica.alcoi.org"
MUNICIPIO = "Alcoy"
ID_PREFIX = "alcoy"
COD_INE_MUN = "03009"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
RSS_URL = f"{WEB_BASE}/es/portal/noticias.rss"
GEOPORTAL_URL = "https://geoportal.alcoi.org/alcoi/"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(0, 16000, 500))

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    f"{WEB_BASE}/es/areas/urbanismo/transparencia/transparencia_urbanismo.html",
    f"{WEB_BASE}/es/areas/urbanismo/transparencia/licencias_urbanisticas.html",
    f"{WEB_BASE}/es/areas/urbanismo/transparencia/declaraciones_obra.html",
    f"{WEB_BASE}/es/areas/urbanismo/transparencia/catalogo_protecciones.html",
    f"{WEB_BASE}/es/areas/urbanismo/transparencia/expedientes_restauracion.html",
    f"{WEB_BASE}/es/areas/urbanismo/poligonos/index.html",
    f"{WEB_BASE}/es/areas/urbanismo/ordenacion.html",
    f"{WEB_BASE}/es/areas/secretaria/convenios.html?area=urbanismo",
    f"{WEB_BASE}/es/areas/urbanismo/tramites/index.html",
    f"{WEB_BASE}/es/areas/urbanismo/index.html",
)

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia urban",
    "licencia de obra",
    "declaración responsable",
    "declaracion responsable",
    "comunicación previa",
    "comunicacion previa",
    "ocupación",
    "ocupacion",
    "proyecto de urbanización",
    "certificado urban",
    "primera ocupación",
    "primera ocupacion",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|listado.*licencia|declaraciones? de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|cat[aà]logo|protecci[oó]|homologaci[oó]n|restablecimiento|"
    r"arranque|reurbanizaci[oó]|alcoidema|alcoiconnecta|industrial|castellar|clerigo|solana)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|subvenci[oó]n|autob[uú]s urbano|impagos de la generalitat|"
    r"ecosistema de innovaci[oó]n|padrones|iae)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _fecha_from_url(url: str) -> str | None:
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url or "") if 1990 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "cat[aà]logo" in n or "catalogo" in n:
        return "catálogo patrimonial"
    if "convenio" in n:
        return "convenio urbanístico"
    if "pol[ií]gono" in n or "poligono" in n:
        return "polígono industrial"
    if "restablecimiento" in n:
        return "restablecimiento legalidad"
    if "licencia" in n or "llicencia" in n:
        return "licencia publicada"
    if "planeam" in n or "urban" in n:
        return "planeamiento"
    return "urbanismo"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        g = feat.get("geometry") if isinstance(feat.get("geometry"), dict) else None
        if not g:
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


class AlcoyAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS alcoi.org + sede STA + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = tuple(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_zones_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-alcoy/1.0"),
                "Accept-Language": "es,ca;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcoy/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _abs_web(self, href: str) -> str:
        return unescape(urljoin(f"{self.web_base}/", href))

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "remitente": str(rem.get("description") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
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
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if "PLAN GENERAL" in norm and "PLAN GENERAL" in den:
                score += 20.0
            if "CLERIGO" in norm and "CLERIGO" in den:
                score += 30.0
            if "CASTELLAR" in norm and "CASTELLAR" in den:
                score += 30.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)

        if best and best[0] >= 20:
            return best[1]
        return None

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

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for zone in self._collect_icv_zones():
            den = zone.get("denominaci") or ""
            exp = zone.get("expediente") or ""
            key = f"icv:{den}:{exp}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": den,
                "fecha": None,
                "tipo": zone.get("tipo") or "planeamiento",
                "url": GEOPORTAL_URL,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": exp if exp and exp != "00000000" else None,
            }
            geom = self._zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_rss_proyectos(self) -> list[dict[str, Any]]:
        try:
            rss = self._fetch(RSS_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in re.findall(r"<item>(.*?)</item>", rss, re.S):
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.S)
            link_m = re.search(r"<link>(.*?)</link>", item, re.S)
            date_m = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
            titulo = _clean_title(title_m.group(1) if title_m else "")
            url = (link_m.group(1) if link_m else "").strip()
            if not titulo or not RE_PROYECTO.search(titulo):
                continue
            if RE_NOISE.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            fecha = _parse_fecha_dmy(date_m.group(1) if date_m else "") if date_m else None
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url or titulo),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": url or RSS_URL,
                "source": "ayuntamiento",
                "origen": "rss_noticias",
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _extract_page_pdfs(self, page_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PDF.findall(html):
            pdf = self._abs_web(href)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = _clean_title(unquote(Path(pdf).name))
            blob = f"{name} {page_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                if not any(
                    k in name.lower()
                    for k in ("urban", "planeam", "licen", "convenio", "catalog", "pol_", "pol-", "pgou")
                ):
                    continue
            rows.append(
                {
                    "titulo": name,
                    "fecha": _fecha_from_url(pdf) or _fecha_from_text(name),
                    "url": page_url,
                    "pdf_url": pdf,
                    "origen": "web_pdf",
                }
            )
        return rows

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            for doc in self._extract_page_pdfs(page_url):
                blob = f"{doc['titulo']} {doc.get('pdf_url', '')}"
                if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", doc["pdf_url"]),
                    "municipio": MUNICIPIO,
                    "titulo": doc["titulo"],
                    "fecha": doc.get("fecha"),
                    "tipo": _proyecto_tipo(blob),
                    "url": doc["url"],
                    "pdf_url": doc["pdf_url"],
                    "source": "ayuntamiento",
                    "origen": doc.get("origen"),
                }
                self._enrich_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_licencia_pdfs(self) -> list[dict[str, Any]]:
        lic_pages = (
            f"{self.web_base}/es/areas/urbanismo/transparencia/licencias_urbanisticas.html",
            f"{self.web_base}/es/areas/urbanismo/transparencia/declaraciones_obra.html",
        )
        rows: list[dict[str, Any]] = []
        for page_url in lic_pages:
            for doc in self._extract_page_pdfs(page_url):
                blob = f"{doc['titulo']} {doc.get('pdf_url', '')}"
                if not RE_LICENCIA.search(blob):
                    continue
                rec: dict[str, Any] = {
                    "id": _stable_id("lic", doc["pdf_url"]),
                    "fecha_concesion": doc.get("fecha"),
                    "tipo": "listado licencias" if "licencia" in blob.lower() else "declaración obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": doc["titulo"],
                    "url": doc["url"],
                    "pdf_url": doc["pdf_url"],
                    "source": "ayuntamiento",
                    "nota": "Listado trimestral/anual en PDF; sin coordenadas por expediente",
                    "origen": "transparencia_pdf",
                }
                rows.append(rec)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')} {row.get('remitente', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia|llicencia", blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('remitente', '')} {row.get('extern', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("extern"):
            rec["expte"] = row["extern"]
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in (
            self._collect_licencia_pdfs()
            + [r for row in self._tablon_rows() if (r := self._tablon_to_licencia(row))]
            + [r for row in self._catalog_rows() if (r := self._tramite_to_licencia(row))]
        ):
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._tablon_rows():
            add(self._row_to_proyecto(row))
        for rec in self._collect_icv_proyectos():
            add(rec)
        for rec in self._collect_web_proyectos():
            add(rec)
        for rec in self._collect_rss_proyectos():
            add(rec)
        for row in self._catalog_rows():
            add(self._row_to_proyecto(row))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "transparencia_pdf_sede"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "icv_wfs_web_sede_rss"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
