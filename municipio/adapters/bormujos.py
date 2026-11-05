from __future__ import annotations

import hashlib
import http.cookiejar
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

WEB_BASE = "https://www.bormujos.es"
SEDE_BASE = "https://sede.bormujos.es"
SEDE_ELECTRONICA = "https://bormujos.sedelectronica.es"
TRANSPARENCIA_BASE = "https://transparencia.bormujos.es"
MUNICIPIO = "Bormujos"
ID_PREFIX = "bormujos"
INE_CODE = "41017"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
ETABLON_URL = f"{WEB_BASE}/actualidad/etablon"
LICYTAL_URL = "https://sedeelectronicadipusevilla.es/LicytalSede/jsp/index.faces?cif=P4101700E"
SITUA_SEARCH_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41017"
URBANISMO_PDF_URL = (
    f"{WEB_BASE}/pdflink/es/b912ac68-b5fd-11e5-8e51-7fb253176922/"
    "Urbanismo-y-Obras-Contenido-de-Urbanismo-y-Obras.pdf?themeconfigpath=/sites/bormujos/.themeconfig"
)

TRANSP_PGOU = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00017/"
)
TRANSP_MOD_PGOU = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00017/"
)
TRANSP_CONVENIOS = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00017/"
)

WEB_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/temas/urbanismo-y-obras/",
    f"{WEB_BASE}/ayuntamiento/delegacionesmunicipales/urbanismo/",
]
BOARD_URLS: list[str] = [
    f"{SEDE_ELECTRONICA}/board",
    f"{SEDE_ELECTRONICA}/transparency",
]
TRANSP_SEED_PAGES = [TRANSP_PGOU, TRANSP_MOD_PGOU, TRANSP_CONVENIOS]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|catalogo|catálogo|consulta p[uú]blica|avance|"
    r"actuaci[oó]n|delimitaci[oó]n|unidad de actuaci[oó]n|situa|dominio|reanudaci[oó]n registral)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"empleo p[uú]blico|auxiliar administr|polic[ií]a local|baja de oficio|"
    r"padr[oó]n de habitante|cobranza en voluntaria|cr[eé]dito extraordinario|"
    r"pleno|servicios sociales|cementerio|jurado|fiestas locales)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|actuaci[oó]n|"
    r"estudio de detalle|modificaci[oó]n del planeamiento|convenio urban|dominio)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|pleno|servicios sociales|subvenci[oó]n|"
    r"empleo p[uú]blico|cobranza|cementerio|padr[oó]n|jurado|fiestas locales|"
    r"electricistas|ppes 20)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://bormujos\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
        "EMPLEO PÚBLICO",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "consulta" in blob and ("pública" in blob or "publica" in blob):
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "dominio" in blob:
        return "expediente de dominio"
    return "urbanismo"


class BormujosAyuntamientoAdapter(AyuntamientoAdapter):
    """SagaSuite bormujos.es + INPRO tablón sede.bormujos.es + sedeelectronica board."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sede_electronica = str(
            self.config.get("sede_electronica") or SEDE_ELECTRONICA
        ).rstrip("/")
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.licytal_url = str(self.config.get("licytal_url") or LICYTAL_URL)
        self.transp_pages = [
            str(u)
            for u in (self.config.get("transparencia_pages") or TRANSP_SEED_PAGES)
        ]
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH_URL)
        self.web_seed_pages = [
            str(u) for u in (self.config.get("web_seed_pages") or WEB_SEED_PAGES)
        ]
        self.board_urls = [str(u) for u in (self.config.get("board_urls") or BOARD_URLS)]
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-bormujos/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def _parse_tablon_html(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in RE_TABLON_ROW.finditer(html):
            row_html = tr.group(1)
            hidden = [
                _strip_html(x)
                for x in re.findall(r'<td class="hidden">(.*?)</td>', row_html, re.S)
            ]
            if len(hidden) < 4:
                continue
            referencia, asunto, url_path = hidden[1], hidden[2], hidden[3]
            celdas = [
                _strip_html(x)
                for x in re.findall(
                    r'<td[^>]*class="celdaGrid"[^>]*>(.*?)</td>', row_html, re.S
                )
            ]
            extracto = celdas[0] if celdas else ""
            origen = celdas[1] if len(celdas) > 1 else ""
            fecha_raw = celdas[2] if len(celdas) > 2 else ""
            url = _abs_url(url_path, self.sede_base)
            titulo = extracto or asunto
            if referencia and referencia not in titulo:
                titulo = f"{titulo} (ref. {referencia})"
            rows.append(
                {
                    "referencia": referencia,
                    "asunto": asunto,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "origen_tablon": origen[:120],
                    "blob": f"{asunto} {extracto} {origen}",
                    "origen": "tablon_inpro",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        sources = [self.tablon_url, ETABLON_URL]
        all_rows: list[dict[str, Any]] = []
        seen_refs: set[str] = set()

        for source in sources:
            try:
                html = self._fetch(source, encoding="latin-1")
            except urllib.error.URLError:
                continue

            pages = {1}
            for m in re.finditer(r"d-16544-p=(\d+)", html):
                pages.add(int(m.group(1)))

            for page in sorted(pages):
                if page == 1:
                    page_html = html
                else:
                    page_url = (
                        f"{self.sede_base}/tablon-1.0/do/anuncio/listado?"
                        f"d-16544-p={page}&ine={INE_CODE}&cmd=ANUN00&opcionMenuIzda=1"
                    )
                    try:
                        page_html = self._fetch(page_url, encoding="latin-1")
                    except urllib.error.URLError:
                        continue
                for row in self._parse_tablon_html(page_html):
                    ref = row.get("referencia") or row["url"]
                    if ref in seen_refs:
                        continue
                    seen_refs.add(ref)
                    all_rows.append(row)
        return all_rows

    def _collect_board(self, board_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(board_url)
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
            url = preview_m.group(1) if preview_m else board_url
            if url.startswith("/"):
                url = f"{self.sede_electronica}{url}"

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
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_all_boards(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for board_url in self.board_urls:
            for item in self._collect_board(board_url):
                key = item.get("expediente") or item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows

    def _collect_transparencia_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.transp_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href, inner in RE_LINK.findall(html):
                title = _strip_html(inner)
                low_href = href.lower()
                if ".pdf" not in low_href and ".galleries/" not in low_href:
                    continue
                if "apple-touch-icon" in low_href or "logo" in low_href:
                    continue
                url = _abs_url(href, self.transparencia_base)
                if url in seen:
                    continue
                seen.add(url)
                if not title:
                    title = url.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url,
                        "page": page_url,
                        "origen": "transparencia_pgou",
                    }
                )
        return rows

    def _collect_web_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "titulo": "Urbanismo y Obras — contenido informativo (PDF portal SagaSuite)",
                "url": URBANISMO_PDF_URL,
                "origen": "web_portal",
            }
        ]
        seen = {URBANISMO_PDF_URL}
        for page_url in self.web_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_PDF_HREF.findall(html):
                url = _abs_url(href, self.web_base)
                if url in seen:
                    continue
                seen.add(url)
                name = Path(urllib.parse.unquote(url.split("?")[0])).stem.replace("-", " ")
                rows.append(
                    {
                        "titulo": f"Documento urbanismo — {name}",
                        "url": url,
                        "page": page_url,
                        "origen": "web_portal",
                    }
                )
        return rows

    def _collect_situa_seed(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Planeamiento urbanístico — SITUA Junta de Andalucía (Bormujos INE 41017)",
                "url": self.situa_url,
                "origen": "situa_junta",
            }
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS"):
            return True
        return bool(RE_TABLON_URBAN.search(blob) or RE_LICENCIA.search(blob))

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in proc or "planeam" in proc or "licencia" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("referencia") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_inpro",
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_TABLON_URBAN.search(blob) and asunto not in (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
        ):
            return None
        key = row.get("referencia") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row["url"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_inpro",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row["url"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _doc_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
        titulo = doc["titulo"]
        url = doc["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _fecha_from_blob(titulo, url),
            "tipo": _proyecto_tipo(titulo, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": doc.get("origen") or "transparencia_pgou",
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico INPRO — sede.bormujos.es (INE 41017)",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", ETABLON_URL),
                "fecha_concesion": None,
                "tipo": "e-tablon embebido en portal municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "E-Tablón de anuncios — bormujos.es",
                "url": ETABLON_URL,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_electronica}/board"),
                "fecha_concesion": None,
                "tipo": "tablón sede electrónica (board)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — bormujos.sedelectronica.es",
                "url": f"{self.sede_electronica}/board",
                "source": "ayuntamiento",
                "origen": "sede_board",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/opencms/sede/index.html"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede OpenCMS)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica GSede — trámites y registro",
                "url": f"{self.sede_base}/opencms/opencms/sede/index.html",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.licytal_url),
                "fecha_concesion": None,
                "tipo": "contratación local (Licyt@l Diputación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licyt@l — contratación local Diputación Sevilla (CIF P4101700E)",
                "url": self.licytal_url,
                "source": "ayuntamiento",
                "nota": "Portal provincial; no expone licencias de obra",
                "origen": "dipusevilla",
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_all_boards():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_all_boards():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_all_boards():
            add(self._board_to_proyecto(item))
        for doc in self._collect_transparencia_documents():
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_web_documents():
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_situa_seed():
            add(self._doc_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_pgou"),
            "web": sum(1 for r in rows if r.get("origen") == "web_portal"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa_junta"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        added = stats["rows"] - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": stats["rows"], "added": max(0, added), "status": "ok", **stats}
