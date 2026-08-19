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
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WEB_BASE = "https://www.gascones.com"
SEDE_BASE = "https://gascones.sedelectronica.es"
TRANSP_BASE = "https://transparencia.gascones.com"
MUNICIPIO = "Gascones"
ID_PREFIX = "gascones"

BOARD_URL = f"{SEDE_BASE}/board/"
NNSS_URL = f"{WEB_BASE}/tu-ayuntamiento/normativa-municipal/urbanismo-normas-subsidiarias"
LICENCIAS_URL = f"{WEB_BASE}/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes"
TRANSP_URB_URL = (
    f"{TRANSP_BASE}/transparencia-en-materias-de-urbanismo-obras-publicas-y-medioambiente"
)
TABLON_RSS = f"{WEB_BASE}/ciudadanos/tablon-municipal?format=feed&type=rss"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=064"

WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "GASCONES"

DEFAULT_URBANISMO_URLS: list[str] = [
    NNSS_URL,
    (
        f"{WEB_BASE}/tu-ayuntamiento/concejalias/129-urbanismo/"
        "417-aprobacion-e-informacion-publica-de-la-modificacion-puntual-de-las-normas-"
        "subsidiarias-de-planeamiento-municipal-de-gascones-en-el-ambito-de-suelo-no-"
        "urbanizable-especialmente-protegido-por-su-interes-agropecuario"
    ),
    (
        f"{WEB_BASE}/tu-ayuntamiento/concejalias/129-urbanismo/"
        "402-anuncio-aprobacion-inicial-de-la-modificacion-puntual-de-las-normas-"
        "subsidiarias-de-planeamiento-municipal-de-gascones-en-el-ambito-del-suelo-no-"
        "urbanizable-especialmente-protegido-de-interes-agropecuario"
    ),
]

AMBITO_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("los redondos", "SAU-1 LOS REDONDOS"),
    ("sau-1", "SAU-1 LOS REDONDOS"),
    ("extension de casco", "E-1 EXTENSIÓN DE CASCO"),
    ("e-1", "E-1 EXTENSIÓN DE CASCO"),
    ("e-2", "E-2 RESIDENCIAL UNIFAMILIAR"),
    ("e-3", "E-3 RESIDENCIAL UNIFAMILIAR"),
    ("e-4", "E-4 RESIDENCIAL UNIFAMILIAR"),
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|segregaci[oó]n|agrupaci[oó]n|vallado|piscina|actividad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|edicto|bocm|ordenanza|parcela|suelo|urbanizaci[oó]n|"
    r"rehabilitaci[oó]n de viviendas|sau-|e-\d|agropecuario|infraestructura)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|activaci[oó]n profesional|despoblamiento|"
    r"censo electoral|electores|subvenci[oó]n.*empleo|turismo|gascones activo|"
    r"calendario fiscal|cobranza.*iae|modificaci[oó]n presupuestaria)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_ ](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DATA_LABEL = re.compile(r'data-label="([^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://gascones\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_ARTICLE_LINK = re.compile(
    r'<a[^>]+href="(/tu-ayuntamiento/concejalias/129-urbanismo/[^"]+)"[^>]*>([^<]{10,500})</a>',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"BOCM[- ]?(\d{1,2})[- ](\d{1,2})[- ](\d{4})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM-(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if re.search(r"\bsau-\d", n):
        return "sector urbanizable"
    if re.search(r"\be-\d", n):
        return "zona urbanística"
    if "bocm" in n:
        return "publicación BOCM"
    if "rehabilitaci" in n:
        return "rehabilitación viviendas"
    return "urbanismo"


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "obra mayor" in n or "lic_obra" in n:
        return "licencia obra mayor"
    if "obra menor" in n or "dru_obra" in n:
        return "declaración responsable obra"
    if "primera ocupaci" in n:
        return "primera ocupación"
    if "actividad" in n:
        return "licencia actividad"
    if "segregaci" in n or "agrupaci" in n:
        return "segregación/agrupación"
    if "vallado" in n:
        return "vallado finca"
    if "piscina" in n:
        return "piscina prefabricada"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "licencia" in n:
        return "modelo licencia"
    return "documento urbanismo"


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("_", " ").replace("-", " ").strip()[:500]


class GasconesAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla LT Company + icagenda tablón + sede espublico + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_urls = [
            str(u) for u in (self.config.get("urbanismo_urls") or DEFAULT_URBANISMO_URLS)
        ]
        self.licencias_url = str(self.config.get("licencias_url") or LICENCIAS_URL)
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-gascones/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str = WEB_BASE) -> str:
        return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href).replace("&amp;", "&"))

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._sitcm_cache is not None:
            return self._sitcm_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{WFS_MUNICIPIO}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache = {}
            return self._sitcm_cache
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        cache = self._load_sitcm_ambitos()
        feat = cache.get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = f"DS_MUNICIPIO='{WFS_MUNICIPIO}' AND DS_NOMB_AMB='{ambit_name.replace(chr(39), chr(39)*2)}'"
        query_url = (
            f"{WFS_BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName={WFS_TYPE}"
            f"&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER={urllib.parse.quote(cql)}"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(WFS_MUNICIPIO, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": WFS_BASE,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        title_low = (title or "").lower()
        for keyword, ambit in AMBITO_KEYWORDS:
            if keyword in title_low:
                hit = self._geometry_from_ambit(ambit)
                if hit:
                    return hit
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells: dict[str, str] = {}
            for label_m in RE_DATA_LABEL.finditer(row_html):
                label = label_m.group(1).strip().lower()
                cells[label] = _strip_html(label_m.group(2))
            if not cells:
                continue
            documento = cells.get("documento", "")
            if documento.lower() == "documento":
                continue

            expediente = cells.get("expediente", "")
            procedimiento = cells.get("procedimiento", "")
            categoria = cells.get("categoría", cells.get("categoria", ""))
            descripcion = cells.get("descripción", cells.get("descripcion", ""))
            fecha_raw = cells.get("fecha de publicación", cells.get("fecha de publicacion", ""))

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw) or _fecha_from_blob(titulo),
                    "url": url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate") or ""
            if not title or not link:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _parse_rss_date(pub),
                    "url": link,
                    "blob": title,
                    "origen": "tablon_web",
                }
            )
        return rows

    def _collect_urbanismo_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.urbanismo_urls:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>\s*([^<]+)", html, re.I)
            page_title = _strip_html(title_m.group(1)) if title_m else page_url
            if page_url not in seen:
                seen.add(page_url)
                rows.append(
                    {
                        "titulo": page_title[:500],
                        "fecha": _fecha_from_blob(page_title),
                        "url": page_url,
                        "tipo": _proyecto_tipo(page_title),
                        "origen": "urbanismo_web",
                    }
                )
            for m in RE_ARTICLE_LINK.finditer(html):
                href = self._abs_url(m.group(1))
                if href in seen:
                    continue
                seen.add(href)
                titulo = _strip_html(m.group(2))
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": href,
                        "tipo": _proyecto_tipo(titulo),
                        "origen": "urbanismo_web",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = _title_from_pdf_url(pdf)
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                        "url": page_url,
                        "pdf_url": pdf,
                        "tipo": _doc_tipo(name),
                        "origen": "urbanismo_web",
                    }
                )
        return rows

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(TRANSP_URB_URL)
        except urllib.error.URLError:
            return rows
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1), self.transp_base)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = _title_from_pdf_url(pdf)
            rows.append(
                {
                    "titulo": f"Infraestructura urbanística — {name}"[:500],
                    "fecha": None,
                    "url": TRANSP_URB_URL,
                    "pdf_url": pdf,
                    "tipo": "infraestructura",
                    "origen": "transparencia",
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.licencias_url)
        except urllib.error.URLError:
            return rows
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = _title_from_pdf_url(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                    "url": self.licencias_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": "tramites_web",
                }
            )
        return rows

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        cache = self._load_sitcm_ambitos()
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for name, feat in cache.items():
            props = feat.get("properties") or {}
            ambit = str(props.get("DS_NOMB_AMB") or "").strip()
            if not ambit or ambit.upper() in seen_names:
                continue
            seen_names.add(ambit.upper())
            fig = str(props.get("DS_CLAS_SUE") or props.get("DS_DOCU") or "").strip()
            titulo = f"{ambit} — {fig}" if fig else ambit
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{ambit}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(ambit),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": ambit,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{WFS_MUNICIPIO}' "
                    f"AND DS_NOMB_AMB='{ambit.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{WFS_BASE}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", NNSS_URL),
                "fecha_concesion": None,
                "tipo": "normas subsidiarias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — Normas Subsidiarias y SITCM",
                "url": NNSS_URL,
                "source": "ayuntamiento",
                "nota": "Cartografía y normativa en visor SIT Comunidad de Madrid",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", self.licencias_url),
                "fecha_concesion": None,
                "tipo": "trámites licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Instancias, licencias y solicitudes — modelos PDF",
                "url": self.licencias_url,
                "source": "ayuntamiento",
                "nota": "Modelos de licencia obra, DR, primera ocupación, etc.",
                "origen": "tramites_web",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y resoluciones publicadas",
                "origen": "tablon_sede",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación de solicitudes",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Registro y consulta de expedientes",
                "origen": "sede_tramites",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        rec = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if RE_EXCLUDE.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo) and row.get("origen") != "sit_wfs":
            return None
        key = row.get("pdf_url") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo),
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo) and row.get("origen") != "tramites_web":
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "modelo licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Modelo o guía de trámite; no concesión publicada",
            "origen": row.get("origen"),
        }

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for doc in self._collect_licencia_tramites():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._collect_licencia_tramites():
            rec = self._doc_to_licencia(doc)
            if rec:
                existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_board():
            add(self._board_to_proyecto(row))
        for row in self._collect_tablon_rss():
            add(self._tablon_to_proyecto(row))
        for row in self._collect_urbanismo_pages():
            add(self._doc_to_proyecto(row))
        for row in self._collect_transparencia_pdfs():
            add(self._doc_to_proyecto(row))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_sede": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "tablon_web": sum(1 for r in rows if r.get("origen") == "tablon_web"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "urbanismo": sum(1 for r in rows if r.get("origen") == "urbanismo_web"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
