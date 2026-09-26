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

WEB_BASE = "https://www.estivella.es"
SEDE_BASE = "https://estivella.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Estivella"
ID_PREFIX = "estivella"
COD_INE_MUN = "46115"

DEFAULT_PAGE_SEEDS: tuple[str, ...] = (
    "/es/pagina/planes-locales",
    "/es/pagina/normas-subsidiarias-planeamiento",
    "/es/pagina/proyectos-ordenanzas",
)

# PDFs estables en planes-locales (investigación sep 2026); fallback si la web hace timeout.
STATIC_PLANES: tuple[dict[str, str], ...] = (
    {
        "titulo": "Plan Territorial Municipal frente a emergencias (PTM Estivella 2023)",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/PTM_Estivella_2023f.pdf"
        ),
        "fecha": "2023-01-01",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Plan Territorial General del T.M. de Estivella",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/PTG%20del%20T.M%20de%20Estivella_firmado.pdf"
        ),
        "fecha": "2025-04-25",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Plan Local de Prevención de Incendios Forestales (PLPIF Estivella 2022)",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/PLPIF%20Estivella%202022_F%20Informado%20Favorable%20por%20GVA.pdf"
        ),
        "fecha": "2022-01-01",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Plan de Movilidad Urbana Sostenible de Estivella (PMUS)",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/Pla%20de%20Mobilitat%20Urbana%20Sostenible%20d%27Estivella%20%28PMUS%29.pdf"
        ),
        "fecha": "2025-04-25",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Plan de actuación municipal frente al riesgo sísmico de Estivella",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/Pla%20actuaci%C3%B3%20municipal%20enfront%20del%20risc%20s%C3%ADsmic%20d%27Estivella.pdf"
        ),
        "fecha": "2025-04-25",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Plan de actuación municipal frente a incendios forestales (PAMIF)",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/Pla%20d%27actuaci%C3%B3n%20municipal%20front%20a%20incendis%20forestals%20%28PAMIF%29.pdf"
        ),
        "fecha": "2025-04-25",
        "path": "/es/pagina/planes-locales",
    },
    {
        "titulo": "Agenda Urbana de Estivella",
        "url": (
            "https://www.estivella.es/sites/www.estivella.es/files/users/user168/"
            "Plans%20Locals/Agenda%20Urbana%20d%27Estivella.pdf"
        ),
        "fecha": "2025-04-25",
        "path": "/es/pagina/planes-locales",
    },
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"compatibilitat urban|compatibilidad urban|certificat.*urban|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|local)|pgou|pla especial|pla urba|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|pr[eè]via)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|cat[aà]leg|protecci[oó]|minimitzaci[oó]|impacte territorial|"
    r"rectificaci[oó]n descriptiva|pl[aà]nol|agenda urbana|pmus|pamif|plpif|ptm|ptg|"
    r"normas subsidiarias|ordenanza|mobilitat|incendi|s[ií]smic|risc)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|nomenament|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó] fiscal|convenis|festiu local|processos selectius|"
    r"auxiliar administrativo|concurs disfresses|bar[oò]metre|jurado|cens electoral|"
    r"arquitecto.*t[eé]cnic)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://estivella\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_FECHA_TEXT = re.compile(
    r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre|gener|febrer|març|abril|maig|juny|"
    r"juliol|agost|setembre|octubre|novembre|desembre)\s+de\s+(\d{4})",
    re.I,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_AVISO_LINK = re.compile(r'href="(/(?:es|va)/pagina-aviso/[^"#?]+)"', re.I)
RE_PAGINA_LINK = re.compile(r'href="(/(?:es|va)/pagina/[^"#?]+)"', re.I)
RE_DATETIME = re.compile(r'datetime="((?:19|20)\d{2}-\d{2}-\d{2})"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_PDF_TITLE = re.compile(
    r'(?:<a[^>]+href="[^"]+\.pdf[^"]*"[^>]*>([^<]+)</a>|'
    r'<span[^>]*>([^<]+\.pdf[^<]*)</span>)',
    re.I,
)

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    "gener": 1,
    "febrer": 2,
    "març": 3,
    "maig": 5,
    "juny": 6,
    "juliol": 7,
    "agost": 8,
    "setembre": 9,
    "novembre": 11,
    "desembre": 12,
}


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


def _parse_fecha_text(text: str) -> str | None:
    m = RE_FECHA_TEXT.search(text or "")
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text) or _parse_fecha_text(text)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _pdf_title_from_url(url: str) -> str:
    name = urllib.parse.unquote(url.split("/")[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("%20", " ").replace("%27", "'")
    return _clean_title(name)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "agenda urbana" in n:
        return "agenda urbana"
    if "pmus" in n or "mobilitat" in n or "movilidad" in n:
        return "plan de movilidad"
    if "pamif" in n or "incendi" in n or "plpif" in n:
        return "plan prevención incendios"
    if "sísmic" in n or "sismic" in n or "riesgo sísmico" in n:
        return "plan riesgo sísmico"
    if "ptm" in n or "emergenc" in n:
        return "plan territorial municipal"
    if "ptg" in n:
        return "plan territorial general"
    if "normas subsidiarias" in n or "normes subsidi" in n:
        return "normas subsidiarias"
    if "ordenanza" in n or "ordenança" in n:
        return "ordenanza"
    if "plan general" in n or "pgou" in n:
        return "plan general"
    if "plan local" in n or "pla local" in n or "planes locales" in n:
        return "plan local"
    return "planeamiento"


class EstivellaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 Portales municipales + sede espublico gestiona (tablón / dossier)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.5))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.page_seeds = tuple(self.config.get("page_seeds") or DEFAULT_PAGE_SEEDS)
        self.static_planes = tuple(self.config.get("static_planes") or STATIC_PLANES)
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 45))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, retries: int = 4) -> str:
        ua = self.config.get("user_agent", "poc-bocm-estivella/1.0")
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": ua,
                    "Accept-Language": "ca,es;q=0.9",
                },
            )
            try:
                with self._opener.open(req, timeout=self.fetch_timeout_s) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(2.0 * (attempt + 1))
        raise last_err or urllib.error.URLError("fetch failed")

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

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

    def _discover_aviso_paths(self) -> list[str]:
        """Avisos urbanísticos (pagina-aviso); la home de Estivella suele hacer timeout SSL."""
        if not self.config.get("discover_from_home", False):
            return []
        paths: set[str] = set()
        for lang in ("es", "va"):
            try:
                html = self._fetch(f"{self.web_base}/{lang}", retries=2)
            except urllib.error.URLError:
                continue
            for m in RE_AVISO_LINK.finditer(html):
                paths.add(m.group(1))
        return sorted(paths)

    def _discover_pagina_paths(self) -> list[str]:
        return list(self.page_seeds)

    def _parse_aviso_page(self, path: str) -> dict[str, Any] | None:
        url = self._abs_web(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        h1 = RE_H1.search(html)
        title_m = RE_TITLE.search(html)
        titulo = _clean_title(h1.group(1) if h1 else (title_m.group(1) if title_m else path))
        titulo = re.sub(r"\s*\|.*Ajuntament.*$", "", titulo, flags=re.I).strip()
        if not titulo or "no trobada" in titulo.lower() or "not found" in titulo.lower():
            return None

        fecha = None
        dt_m = RE_DATETIME.search(html)
        if dt_m:
            fecha = dt_m.group(1)
        if not fecha:
            fecha = _fecha_from_text(html[:8000])

        pdf_urls = [self._abs_web(m.group(1)) for m in RE_PDF.finditer(html)]
        blob = f"{titulo} {path} {' '.join(pdf_urls)}"

        return {
            "titulo": titulo,
            "fecha": fecha,
            "url": url,
            "pdf_urls": pdf_urls,
            "blob": blob,
            "origen": "drupal_aviso",
            "path": path,
        }

    def _parse_pagina_planes(self, path: str) -> list[dict[str, Any]]:
        url = self._abs_web(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        h1 = RE_H1.search(html)
        page_title = _clean_title(h1.group(1) if h1 else path)
        page_fecha = _fecha_from_text(html[:6000])
        rows: list[dict[str, Any]] = []

        for m in RE_PDF.finditer(html):
            href = m.group(1)
            if re.search(r"(?i)calendari|calendar", href):
                continue
            pdf_url = self._abs_web(href)
            titulo = _pdf_title_from_url(href)
            anchor = re.search(
                rf'<a[^>]+href="{re.escape(href)}"[^>]*>([^<]+)</a>',
                html,
                re.I,
            )
            if anchor and anchor.group(1).strip():
                titulo = _clean_title(anchor.group(1))
            rows.append(
                {
                    "titulo": titulo or page_title,
                    "fecha": page_fecha,
                    "url": pdf_url,
                    "pdf_urls": [pdf_url],
                    "blob": f"{titulo} {page_title} {path} {pdf_url}",
                    "origen": "drupal_pagina",
                    "path": path,
                }
            )

        if not rows and RE_PROYECTO.search(page_title):
            rows.append(
                {
                    "titulo": page_title,
                    "fecha": page_fecha,
                    "url": url,
                    "pdf_urls": [],
                    "blob": f"{page_title} {path}",
                    "origen": "drupal_pagina",
                    "path": path,
                }
            )
        return rows

    def _collect_drupal_avisos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in self._discover_aviso_paths():
            if path in seen:
                continue
            seen.add(path)
            item = self._parse_aviso_page(path)
            if item:
                rows.append(item)
        return rows

    def _collect_static_planes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for plan in self.static_planes:
            titulo = plan["titulo"]
            url = plan["url"]
            path = plan.get("path") or "/es/pagina/planes-locales"
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": plan.get("fecha"),
                    "url": url,
                    "pdf_urls": [url],
                    "blob": f"{titulo} {path} {url}",
                    "origen": "drupal_pagina_static",
                    "path": path,
                }
            )
        return rows

    def _collect_drupal_paginas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in self._discover_pagina_paths():
            if path in seen:
                continue
            seen.add(path)
            try:
                parsed = self._parse_pagina_planes(path)
            except urllib.error.URLError:
                parsed = []
            for item in parsed:
                key = item.get("url") or item.get("path") or ""
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        if not rows:
            for item in self._collect_static_planes():
                key = item.get("url") or ""
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
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
                "nota": "Edictos y anuncios publicados en espublico gestiona",
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
                "nota": (
                    "Licencias de obra, comunicaciones previas y certificado de "
                    "compatibilidad urbanística vía sede (sin histórico público)"
                ),
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id(
                    "lic",
                    "https://www.estivella.es/sites/www.estivella.es/files/files/Instancias/"
                    "sollicitud_compatibilitat_urbanistica.pdf",
                ),
                "fecha_concesion": None,
                "tipo": "solicitud compatibilidad urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formulario solicitud certificado/informe compatibilidad urbanística",
                "url": (
                    "https://www.estivella.es/sites/www.estivella.es/files/files/"
                    "Instancias/sollicitud_compatibilitat_urbanistica.pdf"
                ),
                "source": "ayuntamiento",
                "nota": "Modelo PDF en web municipal",
                "origen": "drupal_formulario",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llicència")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _aviso_is_licencia(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob)) and not (
            RE_PROYECTO.search(blob) and "ambiental" not in blob.lower()
        )

    def _aviso_is_proyecto(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if RE_PROYECTO.search(blob):
            return True
        if RE_LICENCIA.search(blob) and "ambiental" in blob.lower():
            return True
        return False

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

    def _aviso_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_licencia(row):
            return None
        blob = row.get("blob") or ""
        tipo = "licencia ambiental" if "ambiental" in blob.lower() else "licencia"
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
            "origen": row.get("origen"),
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

    def _aviso_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_proyecto(row):
            return None
        blob = row.get("blob") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _pagina_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_aviso"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "drupal_formulario")
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
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
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
        for item in self._collect_drupal_avisos():
            add(self._aviso_to_proyecto(item))
        for item in self._collect_drupal_paginas():
            add(self._pagina_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal_aviso": sum(1 for r in rows if r.get("origen") == "drupal_aviso"),
            "drupal_pagina": sum(1 for r in rows if r.get("origen") == "drupal_pagina"),
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
