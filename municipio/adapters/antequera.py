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

WEB_BASE = "https://www.antequera.es"
SEDE_ESPUBLICO = "https://antequera.sedelectronica.es"
SEDE_SWAL = "https://sede.antequera.es"
BOARD_URL = f"{SEDE_ESPUBLICO}/board/"
URBANISMO_TABLON = f"{WEB_BASE}/ayuntamiento/tablon-de-anuncios/Urbanismo/"
ESTABLEC_INFO = (
    f"{WEB_BASE}/ayuntamiento/tablon-de-anuncios/"
    "Establecimientos-y-Actividades-Recreativas/Informacion/"
)
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29015"
MUNICIPIO = "Antequera"
ID_PREFIX = "antequera"
INE_CODE = "29015"

PGOU_SEEDS: list[str] = [
    f"{WEB_BASE}/normativa/plan-general-de-ordenacion-urbanistica/",
    f"{WEB_BASE}/normativa/avance-de-planeamiento-suelo-no-urbanizable/",
    f"{WEB_BASE}/ayuntamiento/transparencia/",
]

TRAMITE_LICENCIA_URLS: list[tuple[str, str]] = [
    (f"{WEB_BASE}/ayuntamiento/tramites/solicitud-de-obras/", "Solicitud de Licencia Municipal de Obra"),
    (
        f"{WEB_BASE}/ayuntamiento/tramites/declaracion-responsable-y-comunicacion-previa-de-inicio-de-obras/",
        "Declaración responsable / comunicación previa de inicio de obras",
    ),
    (
        f"{WEB_BASE}/ayuntamiento/tramites/alta-en-licencia-de-apertura/",
        "Alta en actividades, instalaciones y declaraciones responsables",
    ),
    (
        f"{WEB_BASE}/ayuntamiento/tramites/solicitud-certificados-urbanisticos-o-informaciones-urbanisticas/",
        "Certificados urbanísticos e informaciones urbanísticas",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|expediente apertura|aper\d+|l\.a\.|licencia de apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|reforma)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|pepri|sunc|sup |mejora urbana|planta solar|actuaci[oó]n|proya|"
    r"agenda urbana|ordenanza|normativa urban|visor|situa)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|bolsa de empleo|padrones|cobranza)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://antequera\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_SOLR_ITEM = re.compile(
    r'<h3>\s*<a href="([^"]+)" title="([^"]*)"[^>]*>\s*([^<]*)</a>\s*</h3>\s*'
    r"(?:<p>\s*(.*?)\s*</p>)?.*?<time datetime=\"([^\"]+)\"",
    re.I | re.S,
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_EXPDTE = re.compile(
    r"(?i)(?:exp(?:ediente)?\.?\s*)?(\d{4}-PROYA\d+|\d{4}APER\d+|\d{4}/\d+)",
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


def _parse_iso_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return text.strip()[:10]
    except (TypeError, ValueError):
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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pepri" in b or "dólmenes" in b or "dolmenes" in b:
        return "plan especial patrimonio"
    if "plan parcial" in b or "reforma interior" in b or "sector" in b:
        return "plan parcial / sector"
    if "planta solar" in b or "fotovolta" in b:
        return "actuación energética"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "admisi" in b and "tr" in b and "mite" in b:
        return "admisión a trámite"
    if "agenda urbana" in b:
        return "agenda urbana"
    if "licencia" in b:
        return "licencia publicada"
    if "expediente" in b or "proya" in b:
        return "expediente urbanístico"
    return "urbanismo"


class AntequeraAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Suite (antequera.es tablón Solr) + sede espublico/SWAL + SITUADIFUSION."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_ESPUBLICO).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_tablon = str(self.config.get("urbanismo_tablon") or URBANISMO_TABLON)
        self.establec_info = str(self.config.get("establec_info") or ESTABLEC_INFO)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.pgou_seeds = [str(u) for u in (self.config.get("pgou_seeds") or PGOU_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-antequera/1.0")},
        )
        if use_sede_ssl or "sedelectronica.es" in url:
            with self._opener.open(req, timeout=90) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _tablon_page_urls(self, base: str, param: str, max_page: int) -> list[str]:
        urls = [base if base.endswith("/") else f"{base}/"]
        for n in range(2, max_page + 1):
            urls.append(f"{urls[0]}index.html?{param}={n}")
        return urls

    def _collect_solr_tablon(
        self, base: str, param: str, max_page: int, *, urbanismo: bool
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page_url in self._tablon_page_urls(base, param, max_page):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_SOLR_ITEM.finditer(html):
                href, title_attr, title_text, desc, fecha_iso = m.groups()
                url = self._abs_web(href)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = _strip_html(title_attr or title_text or "")
                descripcion = _strip_html(desc or "")
                blob = f"{title} {descripcion}"
                expte_m = RE_EXPDTE.search(blob) or RE_EXPDTE.search(url)
                rows.append(
                    {
                        "titulo": (descripcion or title)[:500],
                        "short_title": title[:200],
                        "fecha": _parse_iso_date(fecha_iso),
                        "url": url,
                        "blob": blob,
                        "expte": expte_m.group(1) if expte_m else None,
                        "origen": "tablon_urbanismo" if urbanismo else "tablon_actividad",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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
                url = self._abs_sede(url)

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

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.pgou_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = self._abs_web(m.group(1))
                if href in seen:
                    continue
                blob = f"{href} {Path(urllib.parse.unquote(href)).name}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(href)
                name = Path(urllib.parse.unquote(href)).stem.replace("_", " ").replace("-", " ")
                rows.append(
                    {
                        "titulo": f"PGOU / normativa — {name}"[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": href,
                        "blob": blob,
                        "origen": "pgou_pdf",
                    }
                )
        return rows

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón sede espublico",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos en antequera.sedelectronica.es/board",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/ayuntamiento/tablon-de-anuncios/"),
                "fecha_concesion": None,
                "tipo": "tablón web municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Urbanismo y actividades",
                "url": f"{self.web_base}/ayuntamiento/tablon-de-anuncios/",
                "source": "ayuntamiento",
                "nota": "Listados Solr en antequera.es (Urbanismo + Establecimientos)",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", SEDE_SWAL),
                "fecha_concesion": None,
                "tipo": "sede SWAL (trámites)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica sede.antequera.es",
                "url": SEDE_SWAL,
                "source": "ayuntamiento",
                "nota": "Registro y consulta de expedientes (Autofirma); tablón enlaza a web municipal",
                "origen": "sede_tramite",
            },
        ]
        for url, titulo in TRAMITE_LICENCIA_URLS:
            pages.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página de trámite en web municipal (sin listado histórico de concesiones)",
                    "origen": "web_tramite",
                }
            )
        return pages

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if row.get("origen") == "tablon_actividad" or RE_LICENCIA.search(blob):
            key = row.get("expte") or row["url"]
            tipo = "licencia de apertura / actividad"
            if "notificaci" in blob.lower():
                tipo = "notificación licencia"
            return {
                "id": _stable_id("lic", key),
                "fecha_concesion": row.get("fecha"),
                "tipo": tipo,
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": row["titulo"],
                "expte": row.get("expte"),
                "url": row["url"],
                "source": "ayuntamiento",
                "origen": row.get("origen"),
            }
        return None

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if row.get("origen") != "tablon_urbanismo" and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": row.get("origen"),
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
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sede",
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
            "origen": "tablon_sede",
        }

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _situa_row(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.situa_url),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento urbanístico — SITUA Difusión (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": self.situa_url,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": f"PGOU y modificaciones digitalizadas (INE {INE_CODE})",
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
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_solr_tablon(self.establec_info, "psolrlistinfo", 10, urbanismo=False):
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_actividad": sum(1 for r in rows if r.get("origen") == "tablon_actividad"),
            "tablon_sede": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "web_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_solr_tablon(self.establec_info, "psolrlistinfo", 10, urbanismo=False):
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_board():
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
            if rec and rec.get("id") and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        add(self._situa_row())
        for item in self._collect_solr_tablon(self.urbanismo_tablon, "psolrlisturb", 8, urbanismo=True):
            add(self._tablon_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_pgou_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_urbanismo": sum(1 for r in rows if r.get("origen") == "tablon_urbanismo"),
            "tablon_sede": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "pgou_pdf": sum(1 for r in rows if r.get("origen") == "pgou_pdf"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
