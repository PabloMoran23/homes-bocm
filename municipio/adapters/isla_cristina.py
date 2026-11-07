from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://islacristina.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
DOSSIER_URL = f"{SEDE_BASE}/dossier.2"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
WEB_BASE = "https://islacristinaweb.org"
LEGACY_WEB_BASE = "http://wp.islacristina.org"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21043"
SITUA_PGOU_URL = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/"
    "planeamientoGeneralCompartir.jsf?municipiosSeleccionados=21043&codigosMunicipios=21043"
)
VITUA_URL = "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/"
PDC_DIPHUELVA = "https://pdc.diphuelva.es/P2104300D"
MUNICIPIO = "Isla Cristina"
ID_PREFIX = "isla-cristina"
INE_CODE = "21043"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/obras-y-urbanismo/",
    f"{LEGACY_WEB_BASE}/urbanismo-y-obras-publicas/",
    f"{LEGACY_WEB_BASE}/pgou-isla-cristina/",
    f"{LEGACY_WEB_BASE}/planos-pgou-87/",
    f"{WEB_BASE}/servicio-municipal-de-obras-y-urbanismo/",
]

DEFAULT_FORM_LICENCIAS: list[dict[str, str]] = [
    {
        "titulo": "Formulario — Licencia de obra mayor",
        "url": f"{WEB_BASE}/wp-content/uploads/2026/07/Licencia-de-Obra-mayor-2026-formulario.pdf",
    },
    {
        "titulo": "Formulario — Declaración responsable para ejecución de obras",
        "url": f"{WEB_BASE}/wp-content/uploads/2026/07/Declaracion-Responsable-para-ejecucion-de-Obras-2026-Formulario.pdf",
    },
    {
        "titulo": "Formulario — Declaración responsable de ocupación o utilización",
        "url": f"{WEB_BASE}/wp-content/uploads/2026/07/Declaracion-Responsable-de-Ocupacion-o-Utilizacion-2026-formulario.pdf",
    },
    {
        "titulo": "Modelo — Solicitud licencia de apertura",
        "url": f"{WEB_BASE}/wp-content/uploads/2024/05/MODELO-1_SOLICITUD-LICENCIA-DE-APERTURA_2021.pdf",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura| de ocupaci[oó]n)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|formulario)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|ra-pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|subles|"
    r"cambio de uso|ordenanza|actuaci[oó]n urban|situa|vitua|edusi|pmvs|pacto|"
    r"instrumento|convocatoria.*planeamiento|adaptaci[oó]n.*loua)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de (?:empleo|trabajo)|pe[oó]n|auxiliar|subinspector|"
    r"junta general ordinaria|comunidad de regantes|regantes)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://islacristina\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://islacristina\.sedelectronica\.es)?/catalog/t/[a-f0-9-]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_TRANSPARENCY_FOLDER = re.compile(
    r'class="gIconLink exp"[^>]*>([^<]+)<span class="linkExtraInfo">\s*\(\s*(\d+)\s*\)</span>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\']([^"\']+\.(?:pdf|PDF)(?:\?[^"\']*)?)["\']',
    re.I,
)
RE_PAGE_HREF = re.compile(
    r'href=["\']([^"\']*(?:islacristina|planos-pgou|pgou|urbanismo)[^"\']*)["\']',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "edusi" in b or "agenda urbana" in b:
        return "agenda urbana"
    if "pmvs" in b or "plan municipal de vivienda" in b:
        return "plan vivienda y suelo"
    if "estudio de detalle" in b or "api-suz" in b:
        return "estudio de detalle"
    if "convenio" in b:
        return "convenio urbanístico"
    if "plan parcial" in b or "sector" in b or "subles" in b:
        return "plan parcial / sector"
    if "adaptaci" in b and "loua" in b:
        return "adaptación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b or "situa" in b or "vitua" in b:
        return "planeamiento"
    return "urbanismo"


class IslaCristinaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress islacristinaweb.org + legacy wp.islacristina.org + sede espublico gestiona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.legacy_web_base = str(self.config.get("legacy_web_base") or LEGACY_WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.situa_search = str(self.config.get("situa_search_url") or SITUA_SEARCH)
        self.situa_pgou_url = str(self.config.get("situa_pgou_url") or SITUA_PGOU_URL)
        self.pdc_url = str(self.config.get("pdc_url") or PDC_DIPHUELVA)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.form_licencias = list(self.config.get("form_licencias") or DEFAULT_FORM_LICENCIAS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch_sede(self, url: str) -> str:
        last_err: Exception | None = None
        for attempt in range(3):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-isla-cristina/1.0")},
            )
            try:
                with self._opener.open(req, timeout=75) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(1.0 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_web(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-isla-cristina/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch(self, url: str) -> str:
        if "sedelectronica.es" in url:
            return self._fetch_sede(url)
        return self._fetch_web(url)

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("http://") or href.startswith("https://"):
            return href
        root = base or self.web_base
        return urllib.parse.urljoin(f"{root}/", href)

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
                cells[cm.group(1)] = _strip_html(cm.group(2))

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

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href = m.group(1)
            title = _strip_html(m.group(2))
            if href.startswith("/"):
                href = f"{self.sede_base}{href}"
            if href in seen or not title:
                continue
            if not RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
                continue
            seen.add(href)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": None,
                    "url": href,
                    "procedimiento": "catálogo sede",
                    "blob": title,
                }
            )
        return rows

    def _collect_transparency_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_TRANSPARENCY_FOLDER.finditer(html):
            title = _strip_html(m.group(1))
            count = m.group(2) or ""
            if not title:
                continue
            combined = f"{title} ({count} documentos)" if count else title
            if not RE_PROYECTO.search(combined):
                continue
            rows.append(
                {
                    "titulo": combined[:500],
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": title,
                    "blob": combined,
                }
            )

        for m in re.finditer(
            r'href="((?:https://islacristina\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
            r'[^>]*title="([^"]+)"',
            html,
            re.I,
        ):
            doc_url = m.group(1)
            if doc_url.startswith("/"):
                doc_url = f"{self.sede_base}{doc_url}"
            if doc_url in seen:
                continue
            seen.add(doc_url)
            title = unescape(m.group(2).strip())
            if not title or not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(title),
                    "url": doc_url,
                    "procedimiento": "transparencia",
                    "blob": title,
                }
            )
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        visited_pages: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        seen_pdfs: set[str] = set()
        rows: list[dict[str, Any]] = []

        while queue and len(visited_pages) < 24:
            page_url = queue.pop(0)
            page_url = self._abs_url(page_url)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError):
                continue

            for m in RE_PAGE_HREF.finditer(html):
                next_url = self._abs_url(m.group(1))
                if (
                    "islacristina" in next_url
                    and next_url not in visited_pages
                    and next_url not in queue
                    and len(queue) < 30
                ):
                    queue.append(next_url)

            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_url(m.group(1))
                pdf_url = urllib.parse.unquote(pdf_url)
                if pdf_url in seen_pdfs:
                    continue
                title = _pdf_title(pdf_url)
                blob = f"{title} {pdf_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen_pdfs.add(pdf_url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_proyecto_static(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.situa_pgou_url),
                "municipio": MUNICIPIO,
                "titulo": "RA-PGOU Isla Cristina — documentación en SITUA (CP-158/2012)",
                "fecha": "2013-03-20",
                "tipo": "PGOU",
                "url": self.situa_pgou_url,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": f"Planeamiento general aprobado (INE {INE_CODE})",
            },
            {
                "id": _stable_id("proy", self.situa_search),
                "municipio": MUNICIPIO,
                "titulo": "Consulta planeamiento — SITUADIFusión (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.situa_search,
                "source": "ayuntamiento",
                "origen": "situa",
            },
            {
                "id": _stable_id("proy", VITUA_URL),
                "municipio": MUNICIPIO,
                "titulo": "Visor territorial y urbanístico VITUA — Junta de Andalucía",
                "fecha": None,
                "tipo": "visor urbanístico",
                "url": VITUA_URL,
                "source": "ayuntamiento",
                "origen": "vitua",
            },
            {
                "id": _stable_id("proy", self.pdc_url),
                "municipio": MUNICIPIO,
                "titulo": "PDC Diputación Huelva — planeamiento y cartografía municipal",
                "fecha": None,
                "tipo": "cartografía urbanística",
                "url": self.pdc_url,
                "source": "ayuntamiento",
                "origen": "pdc",
            },
            {
                "id": _stable_id("proy", f"{self.legacy_web_base}/pgou-isla-cristina/"),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Isla Cristina — normas, modificaciones y planos (web municipal)",
                "fecha": None,
                "tipo": "PGOU",
                "url": f"{self.legacy_web_base}/pgou-isla-cristina/",
                "source": "ayuntamiento",
                "origen": "web_pgou",
            },
            {
                "id": _stable_id("proy", f"{LEGACY_WEB_BASE}/urbanismo-y-obras-publicas/"),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo y obras públicas — instrumentos y convenios (web)",
                "fecha": None,
                "tipo": "urbanismo",
                "url": f"{LEGACY_WEB_BASE}/urbanismo-y-obras-publicas/",
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — Obras y Urbanismo",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Licencias, comunicaciones previas y actuaciones urbanísticas",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/obras-y-urbanismo/"),
                "fecha_concesion": None,
                "tipo": "formularios licencias y actividades",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios de licencias y declaraciones responsables",
                "url": f"{self.web_base}/obras-y-urbanismo/",
                "source": "ayuntamiento",
                "nota": "Modelos PDF descargables (obra, actividad, DR)",
                "origen": "web_formularios",
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
                "nota": "Requiere identificación; sin listado público de concesiones",
                "origen": "sede_tramite",
            },
        ]
        for form in self.form_licencias:
            url = str(form.get("url") or "").strip()
            titulo = str(form.get("titulo") or "").strip()
            if not url or not titulo:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _fecha_from_blob(titulo + " " + url),
                    "tipo": "formulario trámite",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "web_formulario",
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genérico")):
            return True
        if "urbanismo" in cat:
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
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
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

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row["titulo"][:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_catalogo",
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not re.search(r"(?i)planeam|modificaci|actuaci", blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_catalogo",
        }

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "web_pdf",
        }

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia",
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "sede_catalogo"),
            "info": sum(
                1
                for r in rows
                if r.get("origen")
                in ("sede_tablon", "sede_tramite", "web_formularios", "web_formulario")
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
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
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

        for rec in self._collect_proyecto_static():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_transparency_docs():
            add(self._transparency_to_proyecto(item))
        for item in self._collect_web_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "sede_catalogo"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "situa": sum(1 for r in rows if r.get("origen") in ("situa", "vitua", "pdc")),
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
