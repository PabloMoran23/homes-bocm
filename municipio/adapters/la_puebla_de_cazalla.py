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

SEDE_BASE = "https://lapuebladecazalla.sedelectronica.es"
WEB_BASE = "http://www.pueblacazalla.org/ayto"
TRANSPARENCIA_BASE = "https://transparencia.lapuebladecazalla.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "La Puebla de Cazalla"
ID_PREFIX = "la-puebla-de-cazalla"

PGOU_INDEX_URL = (
    f"{WEB_BASE}/index.php/la-puebla-de-cazalla/60-ayuntamiento/urbanismo/762-pgou-indice"
)
TRANSP_URBANISMO_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/"
    "indicador/50.-INSTRUMENTOS-DE-PLANEAMIENTO-URBANISTICO-MUNICIPAL./"
)

DEFAULT_SEED_PAGES: list[str] = [
    PGOU_INDEX_URL,
    f"{WEB_BASE}/index.php/elayuntamiento/urbanismo",
    f"{WEB_BASE}/index.php/elayuntamiento/urbanismo/ordenacion-de-obras-y-actividades",
    f"{WEB_BASE}/index.php/elayuntamiento/urbanismo/obras-en-ejecucion",
    TRANSP_URBANISMO_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|puc|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|nnss|normas urban|catalogo|catálogo|consulta p[uú]blica|"
    r"urbanizaci[oó]n|ur-\d|actuaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|padr[oó]n|tasas municipales|"
    r"anuncio.*bop n|pefea|monitores)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://lapuebladecazalla\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_JOOMLA_PDF = re.compile(
    r'href="((?:https?://www\.pueblacazalla\.org)?/ayto/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TRANSP_PDF = re.compile(
    r'href="((?:https?://transparencia\.lapuebladecazalla\.es)?/export/[^"]+\.(?:pdf|PDF)[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_UR_CODE = re.compile(r"(?i)\b(UR-\d+)\b")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_web_url(href: str) -> str:
    return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href))


def _abs_transp_url(href: str) -> str:
    return urllib.parse.urljoin(f"{TRANSPARENCIA_BASE}/", unescape(href))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if re.search(r"(?i)\bur-\d+", blob):
        return "actuación urbanística"
    if "plan parcial" in blob or " pp " in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "pgou" in blob or "plan general" in blob or "puc" in blob:
        return "PGOU"
    if "nnss" in blob or "normas subsidiarias" in blob:
        return "normas subsidiarias"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob or "normas urban" in blob:
        return "ordenanza urbanística"
    if "urbanizaci" in blob:
        return "proyecto de urbanización"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class LaPueblaDeCazallaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla web (pueblacazalla.org) + sede espublico gestiona + transparencia Diputación Sevilla."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.pgou_index_url = str(self.config.get("pgou_index_url") or PGOU_INDEX_URL)
        self.transp_urbanismo_url = str(
            self.config.get("transp_urbanismo_url") or TRANSP_URBANISMO_URL
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "poc-bocm-la-puebla-de-cazalla/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

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

    def _collect_joomla_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page_url in self.seed_pages:
            if not page_url.startswith(self.web_base):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_JOOMLA_PDF.finditer(html):
                pdf_url = _abs_web_url(m.group(1))
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)
                link_text = ""
                for am in re.finditer(
                    rf'href="{re.escape(m.group(1))}"[^>]*>(.*?)</a>',
                    html,
                    re.I | re.S,
                ):
                    link_text = _strip_html(am.group(1))
                    break
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
                titulo = link_text or name
                if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(pdf_url):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo, pdf_url),
                        "url": pdf_url,
                        "procedimiento": "documentación urbanismo",
                        "blob": f"{titulo} {pdf_url}",
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_transparencia(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.transp_urbanismo_url)
        except urllib.error.URLError:
            return rows

        seen: set[str] = set()
        for m in RE_TRANSP_PDF.finditer(html):
            pdf_url = _abs_transp_url(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
            titulo = name.replace("_", " ")
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo, pdf_url),
                    "url": pdf_url,
                    "procedimiento": "transparencia planeamiento",
                    "blob": f"{titulo} transparencia planeamiento",
                }
            )

        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
            href, text = m.group(1), _strip_html(m.group(2))
            if "pgou" not in f"{href} {text}".lower():
                continue
            url = href if href.startswith("http") else _abs_transp_url(href)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": text[:500] or "PGOU — información pública",
                    "fecha": _fecha_from_blob(text, url),
                    "url": url,
                    "procedimiento": "transparencia PGOU",
                    "blob": f"{text} PGOU",
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
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede electrónica espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/info"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/info",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/index.php/elayuntamiento/urbanismo/ordenacion-de-obras-y-actividades"),
                "fecha_concesion": None,
                "tipo": "ordenación de obras y actividades",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenación de obras y actividades — web municipal",
                "url": f"{self.web_base}/index.php/elayuntamiento/urbanismo/ordenacion-de-obras-y-actividades",
                "source": "ayuntamiento",
                "nota": "Información de trámites de licencias en web Joomla",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if (
            RE_BOARD_NON_URBAN.search(blob)
            and not RE_LICENCIA.search(blob)
            and not RE_PROYECTO.search(blob)
        ):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(
            k in proc or k in cat
            for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "actuaci")
        ):
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
        if not RE_PROYECTO.search(blob) and "actuaci" not in proc and "urban" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _doc_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        titulo = row["titulo"]
        ur = RE_UR_CODE.search(titulo)
        key = ur.group(1).upper() if ur else row["url"]
        return {
            "id": _stable_id("proy", f"{origen}:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": origen,
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
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
        for item in self._collect_joomla_pdfs():
            add(self._doc_to_proyecto(item, "joomla_pdf"))
        for item in self._collect_transparencia():
            add(self._doc_to_proyecto(item, "transparencia"))

        add(
            {
                "id": _stable_id("proy", self.pgou_index_url),
                "municipio": MUNICIPIO,
                "titulo": "PGOU — índice documentación y tramitación (web municipal)",
                "fecha": "2020-01-01",
                "tipo": "PGOU",
                "url": self.pgou_index_url,
                "source": "ayuntamiento",
                "origen": "joomla_pgou",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "joomla": sum(1 for r in rows if str(r.get("origen", "")).startswith("joomla")),
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
