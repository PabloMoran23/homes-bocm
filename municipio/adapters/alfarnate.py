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

WEB_BASE = "https://www.alfarnate.es"
SEDE_LOCAL = "https://alfarnate.sedelectronica.es"
SEDE_DIPU = "https://sede.malaga.es/alfarnate"
GOBIERNO_ABIERTO = "https://www.malaga.es/gobiernoabierto/alfarnate"
PGOU_URL = f"{WEB_BASE}/3253/pgou-alfarnate"
URBANISMO_URL = f"{WEB_BASE}/14578/com1_md1_cd-18748/urbanismo"
LICENCIAS_URL = f"{WEB_BASE}/14578/com1_md1_cd-18746/licencias-y-permisos-municipales"
TRAMITES_URL = f"{WEB_BASE}/3263/tramites-en-linea"
ORDENANZA_URL = (
    f"{WEB_BASE}/81/com1_md3_cd-70655/publicacion-texto-del-proyecto-de-ordenanza?com1_md=3"
)
PLANEAMIENTO_FICHA = (
    "https://www.malaga.es/delegacionfomento/planeamiento/ficha.asp?mun=29003&cod=736"
)
MUNICIPIO = "Alfarnate"
ID_PREFIX = "alfarnate"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es",
    PGOU_URL,
    URBANISMO_URL,
    LICENCIAS_URL,
    TRAMITES_URL,
    ORDENANZA_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|permiso municipal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n descriptiva|divisi[oó]n|segregaci[oó]n|"
    r"innovaci[oó]n|normativa urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|bolsa de trabajo|subvenci[oó]n|contrataci[oó]n|"
    r"modificaci[oó]n de cr[eé]dito|empleo p[uú]blico)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://alfarnate\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
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


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "innovaci" in blob:
        return "innovación PGOU"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class AlfarnateAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Diputación Málaga (alfarnate.es) + sede centralizada Diputación; sede local inactiva."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_local = str(self.config.get("sede_local") or SEDE_LOCAL).rstrip("/")
        self.sede_dipu = str(self.config.get("sede_dipu") or SEDE_DIPU).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_local}/board/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
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
                    "Mozilla/5.0 (compatible; poc-bocm-alfarnate/1.0)",
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        if len(text) < 200 and "awsWaf" in text:
            raise urllib.error.URLError("AWS WAF challenge")
        return text

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.web_base, href))

    def _sede_is_inactive(self, html: str) -> bool:
        return "inactiva" in (html or "").lower()

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        if self._sede_is_inactive(html):
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
                url = f"{self.sede_local}{url}"

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", LICENCIAS_URL),
                "fecha_concesion": None,
                "tipo": "licencias y permisos municipales",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias y permisos municipales — web ayuntamiento",
                "url": LICENCIAS_URL,
                "source": "ayuntamiento",
                "nota": "Información y modelos de solicitud; sin listado histórico de concesiones",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", TRAMITES_URL),
                "fecha_concesion": None,
                "tipo": "trámites en línea",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites en línea — sede Diputación Málaga",
                "url": TRAMITES_URL,
                "source": "ayuntamiento",
                "nota": "Acceso a sede electrónica centralizada de la Diputación",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.sede_dipu),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Alfarnate (Diputación Málaga)",
                "url": self.sede_dipu,
                "source": "ayuntamiento",
                "nota": "Trámites de licencias y urbanismo vía sede centralizada",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón sede local (inactiva)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede local (temporalmente inactiva)",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "alfarnate.sedelectronica.es devuelve página de sede inactiva",
                "origen": "sede_tablon",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", PGOU_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Alfarnate — documentación municipal",
                "fecha": "2011-01-01",
                "tipo": "PGOU",
                "url": PGOU_URL,
                "source": "ayuntamiento",
                "origen": "web_pgou",
            },
            {
                "id": _stable_id("proy", PLANEAMIENTO_FICHA),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Alfarnate — ficha planeamiento Diputación Málaga",
                "fecha": "2011-01-01",
                "tipo": "PGOU",
                "url": PLANEAMIENTO_FICHA,
                "source": "ayuntamiento",
                "origen": "diputacion_planeamiento",
            },
            {
                "id": _stable_id("proy", ORDENANZA_URL),
                "municipio": MUNICIPIO,
                "titulo": "Publicación texto del proyecto de ordenanza",
                "fecha": None,
                "tipo": "ordenanza urbanística",
                "url": ORDENANZA_URL,
                "source": "ayuntamiento",
                "origen": "web_normativa",
            },
            {
                "id": _stable_id("proy", URBANISMO_URL),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo — concejalía y documentación",
                "fecha": None,
                "tipo": "urbanismo",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
            },
            {
                "id": _stable_id("proy", GOBIERNO_ABIERTO),
                "municipio": MUNICIPIO,
                "titulo": "Gobierno abierto Alfarnate — información urbanística",
                "fecha": None,
                "tipo": "urbanismo",
                "url": GOBIERNO_ABIERTO,
                "source": "ayuntamiento",
                "origen": "diputacion_transparencia",
            },
        ]

    def _is_doc_href(self, href: str) -> bool:
        h = href.lower()
        return bool(
            re.search(r"(?i)\.(pdf|zip|docx?)(?:\?|$)", h)
            or "preview-document" in h
            or "subidas/archivos" in h
        )

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            if len(html) < 500:
                continue

            page_title = ""
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            if title_m:
                page_title = _strip_html(title_m.group(1))

            for m in RE_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if href.startswith("#") or "favicon" in href.lower():
                    continue
                url = self._abs_url(href, page_url)
                blob = f"{anchor} {page_title} {url}"
                if not (self._is_doc_href(url) or RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                    continue
                if url in seen:
                    continue
                seen.add(url)

                titulo = anchor or page_title or Path(url).name
                if len(titulo) < 4:
                    titulo = page_title or titulo

                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "page": page_url,
                    }
                )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
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
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        if not RE_PROYECTO.search(urban_blob) and "planeamiento" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento general|aprobaci[oó]n inicial|pgou", blob):
            tipo = "PGOU"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)ordenanza", blob):
            tipo = "ordenanza urbanística"

        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
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
            "tipo": _proyecto_tipo(row["titulo"], row["url"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "web_crawl",
        }

    def _seed_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / trámite urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "web_crawl",
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
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite", "web_crawl")
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
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "static": sum(
                1
                for r in rows
                if r.get("origen")
                in (
                    "web_pgou",
                    "diputacion_planeamiento",
                    "web_normativa",
                    "web_urbanismo",
                    "diputacion_transparencia",
                )
            ),
            "crawl": sum(1 for r in rows if r.get("origen") == "web_crawl"),
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
