from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.antas.es"
WP_API = f"{WEB_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://antas.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
URBANISMO_URL = f"{WEB_BASE}/urbanismo/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Antas"
ID_PREFIX = "antas"
COD_INE = "04016"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

WP_SEARCH_TERMS = (
    "planeamiento",
    "pgou",
    "pbom",
    "poligono industrial",
    "sector SR",
    "modificacion puntual",
    "licencia obra",
    "planta solar",
    "regularizacion",
    "urbanismo",
    "el real",
    "aljoroque",
)

DEFAULT_WP_SEED_URLS: tuple[str, ...] = (
    f"{WEB_BASE}/plan-basico-de-ordenacion-municipal/",
    f"{WEB_BASE}/proyecto-de-mejora-y-modernizacion-de-infraestructuras-en-el-poligono-industrial-de-el-real-programa-de-actuaciones-conjuntas-de-dotacion-y-modernizacion-de-espacios-productivos-y-de-innovacion-pep/",
    f"{WEB_BASE}/hito-historico-tras-34-anos-de-espera-regularizacion-del-poligono-industrial-sector-sr-1-aljoroque/",
    f"{WEB_BASE}/aprobacion-provisional-de-la-modificacion-puntual-del-pgou-de-antas-para-el-sector-sr-6/",
    f"{WEB_BASE}/antas-hace-historia-aprobacion-definitiva-del-poligono-industrial-aljoroque-sr-1/",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|permiso para instalarse)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pgou|pbom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bopma|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|pol[ií]gono industrial|regularizaci[oó]n|planta solar|"
    r"normas urban|edificaci[oó]n|ordenaci[oó]n municipal)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(bando.*limpieza|limpieza de solares|limpieza de terrenos|"
    r"memoria explicativa del presupuesto|fiestas|recreaci[oó]n hist[oó]rica|"
    r"taller pr[aá]ctico|banda ancha|fibra [oó]ptica|cementerio|"
    r"seguridad ciudadana|carreteras m[aá]s seguras|asfalto del camino|"
    r"medalla de la cultura|visita.*diputaci[oó]n|edificio polivalente(?!.*licencia))",
)
RE_EXCLUDE_TITLE = re.compile(
    r"(?i)^(punto limpio|bando municipal|normativa para la regulaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaciones presupuestarias|mod\. del presupuesto|"
    r"crédito extraordinario|mercadillo|fiestas|jurado|bando limpieza)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://antas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_DOC = re.compile(
    r'href="((?:https://www\.antas\.es)?/wp-content/uploads/[^"]+\.(?:pdf|odt|docx?)[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)\b(SR-\d+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñ]+)?|EL REAL(?:\s+[A-Z]+)?|PARAJE\s+[A-ZÁÉÍÓÚ]+)\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "modificaci" in b and ("pgou" in b or "puntual" in b):
        return "modificación puntual PGOU"
    if re.search(r"sr-\d", b):
        return "sector planeamiento"
    if "pol[ií]gono industrial" in b or "poligono industrial" in b:
        return "polígono industrial"
    if "planta solar" in b or "parque solar" in b:
        return "instalación solar"
    if "regularizaci" in b:
        return "regularización urbanística"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "aprobaci" in b and "definitiva" in b:
        return "aprobación definitiva"
    if "aprobaci" in b and "provisional" in b:
        return "aprobación provisional"
    return "urbanismo"


class AntasAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress www.antas.es + sede espublico gestiona + WFS Dipalme (sectores SIU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api_base") or f"{self.web_base}/wp-json/wp/v2").rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.wp_search_terms = list(self.config.get("wp_search_terms") or WP_SEARCH_TERMS)
        self.wp_seed_urls = tuple(self.config.get("wp_seed_urls") or DEFAULT_WP_SEED_URLS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-antas/1.0")},
        )
        if insecure is False:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urljoin(f"{self.web_base}/", unescape(href).replace("&amp;", "&"))

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

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(WFS_SECTORS_URL)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": _norm_text(sector),
                        "geom": geom,
                        "cod_ine": props.get("cod_ine"),
                        "clase_suelo": props.get("clase_suelo"),
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        result: dict[str, Any] | None = None

        for m in RE_SECTOR.finditer(title):
            token = _norm_text(m.group(1))
            if len(token) < 3:
                continue
            for row in self._load_sectors():
                sector_norm = row["sector_norm"]
                if token in sector_norm or sector_norm in title_norm:
                    geom = row["geom"]
                    sector_escaped = row["sector"].replace("'", "''")
                    cql = urllib.parse.quote(
                        f"cod_ine='{COD_INE}' AND sector='{sector_escaped}'"
                    )
                    query = (
                        "https://app.dipalme.org/geoserver/urbanismo/ows?"
                        "service=WFS&version=2.0.0&request=GetFeature&"
                        "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                        f"CQL_FILTER={cql}&"
                        "count=1&outputFormat=application/json&srsName=EPSG:4326"
                    )
                    result = {
                        "geom_geojson": geom,
                        "geometry_source": "dipalme_wfs_sector",
                        "geometry_source_url": query,
                        "coord_source": "portal_geometry_centroid",
                        "sector_urbanistico": row["sector"],
                    }
                    centroid = geometry_centroid(geom)
                    if centroid:
                        result["lat"], result["lon"] = centroid
                    break
            if result:
                break

        if not result:
            for row in self._load_sectors():
                sector_norm = row["sector_norm"]
                if len(sector_norm) < 5:
                    continue
                if sector_norm in title_norm or re.search(
                    rf"\b{re.escape(sector_norm)}\b", title_norm
                ):
                    geom = row["geom"]
                    sector_escaped = row["sector"].replace("'", "''")
                    cql = urllib.parse.quote(
                        f"cod_ine='{COD_INE}' AND sector='{sector_escaped}'"
                    )
                    query = (
                        "https://app.dipalme.org/geoserver/urbanismo/ows?"
                        "service=WFS&version=2.0.0&request=GetFeature&"
                        "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                        f"CQL_FILTER={cql}&"
                        "count=1&outputFormat=application/json&srsName=EPSG:4326"
                    )
                    result = {
                        "geom_geojson": geom,
                        "geometry_source": "dipalme_wfs_sector",
                        "geometry_source_url": query,
                        "coord_source": "portal_geometry_centroid",
                        "sector_urbanistico": row["sector"],
                    }
                    centroid = geometry_centroid(geom)
                    if centroid:
                        result["lat"], result["lon"] = centroid
                    break

        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry_for_title(rec.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _wp_post_row(self, post: dict[str, Any]) -> dict[str, Any] | None:
        link = str(post.get("link") or "")
        if not link:
            return None
        title = _clean_title(post.get("title", {}).get("rendered") or "")
        excerpt = _strip_html(post.get("excerpt", {}).get("rendered") or "")
        blob = f"{title} {excerpt}"
        if RE_EXCLUDE_TITLE.search(title) or RE_EXCLUDE.search(title):
            return None
        if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        return {
            "titulo": title,
            "fecha": _fecha_from_text(f"{post.get('date', '')} {blob}"),
            "url": link,
            "blob": blob,
            "origen": "wp_post",
        }

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen_links: set[str] = set()
        rows: list[dict[str, Any]] = []
        for seed_url in self.wp_seed_urls:
            slug = seed_url.rstrip("/").split("/")[-1]
            try:
                posts = self._fetch_json(
                    f"{self.wp_api}/posts?slug={urllib.parse.quote(slug)}&status=publish"
                )
            except (urllib.error.URLError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                row = self._wp_post_row(post)
                if row and row["url"] not in seen_links:
                    seen_links.add(row["url"])
                    rows.append(row)
        for term in self.wp_search_terms:
            try:
                url = (
                    f"{self.wp_api}/posts?search={urllib.parse.quote(term)}"
                    "&per_page=50&status=publish"
                )
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                row = self._wp_post_row(post)
                if row and row["url"] not in seen_links:
                    seen_links.add(row["url"])
                    rows.append(row)
        return rows

    def _collect_urbanismo_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url, insecure=False)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_DOC.finditer(html):
            url = self._abs_web(m.group(1))
            if url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url.split("?")[0]).name))
            name = re.sub(r"\.(pdf|odt|docx?)$", "", name, flags=re.I)
            name = name.replace("-", " ").replace("_", " ")
            title = _clean_title(name)
            rows.append(
                {
                    "titulo": title,
                    "fecha": _fecha_from_text(url),
                    "url": url,
                    "blob": title,
                    "origen": "urbanismo_doc",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "modelos licencias y declaraciones responsables",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — modelos DR y comunicación previa",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios DR obras, ocupación y comunicación previa en web municipal",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if "presupuest" in proc:
            return False
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        return self._enrich_geometry(rec)

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        title = row.get("titulo") or ""
        if RE_EXCLUDE_TITLE.search(title) or RE_EXCLUDE.search(title):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "wp_post",
        }
        return self._enrich_geometry(rec)

    def _wp_doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "comunicacion" not in blob.lower():
            return None
        tipo = "declaración responsable / comunicación previa"
        if "obra" in blob.lower():
            tipo = "declaración responsable de obras"
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "urbanismo_doc",
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_urbanismo_docs():
            rec = self._wp_doc_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite", "urbanismo_doc")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_urbanismo_docs():
            rec = self._wp_doc_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_urbanismo_docs():
            blob = item.get("blob") or ""
            if RE_PROYECTO.search(blob):
                add(self._wp_to_proyecto(item))

        situa_rec = {
            "id": _stable_id("proy", SITUA_SEARCH),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento urbanístico — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": SITUA_SEARCH,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional SITUADIFusión para PGOU/PBOM aprobados",
        }
        add(situa_rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wp": sum(1 for r in rows if r.get("origen") in ("wp_post", "urbanismo_doc")),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
