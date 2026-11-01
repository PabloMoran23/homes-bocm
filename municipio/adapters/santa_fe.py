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

WEB_BASE = "http://www.santafe.es"
URBANISMO_URL = (
    "http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob="
    "&sp=fd758a562efe887ea5300b37463fe9e3"
)
PLANEAMIENTO_URL = (
    "http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob="
    "&sp=fd758a562efe887ea5300b37463fe9e3&spp=767729668d7e514416a282aeaa988187"
)
FORMULARIOS_URL = (
    "http://www.santafe.es/index.php?g=1&c=2&c2=&f1=contenidos&s1=see&f2=&s2=&ob="
    "&spp=04a26d0be3e8a8c1ef3fd08330825579"
)
SEDE_BASE = "https://santafe.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
VITUA_URL = (
    "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/"
)
INE_MUNICIPIO = "18175"
MUNICIPIO = "Santa Fe"
ID_PREFIX = "santa-fe"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|parcelaci[oó]n|ocupaci[oó]n de v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|consulta p[uú]blica|expropiaci[oó]n|clasificaci[oó]n|"
    r"calificaci[oó]n|zonificaci[oó]n|unidad de ejecuci[oó]n|ue-\d+)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|elecciones|censo electoral|bando.*electoral|"
    r"subasta|regantes|comunidad de regantes|empleo@|programa municipal de empleo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://santafe\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_ARTICO_PDF = re.compile(
    r"MM_openBrWindow\('(data/ficherosadjuntos[^']+\.pdf)'[^>]*>([^<]+)</a>",
    re.I | re.S,
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b or re.search(r"\bue[- ]?\d+", b):
        return "plan parcial / unidad de ejecución"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "plano" in b or "clasificaci" in b or "zonificaci" in b:
        return "cartografía urbanística"
    if "expropiaci" in b:
        return "expropiación"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class SantaFeAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Artico Estudio (santafe.es) + sede espublico gestiona (tablón /board/)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.formularios_url = str(self.config.get("formularios_url") or FORMULARIOS_URL)
        self.ine_municipio = str(self.config.get("ine_municipio") or INE_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
    def _fetch(self, url: str, *, charset_hint: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santa-fe/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = charset_hint or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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

    def _collect_planeamiento_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.planeamiento_url, charset_hint="iso-8859-1")
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_ARTICO_PDF.finditer(html):
            rel_path = m.group(1)
            titulo = _strip_html(m.group(2)) or Path(rel_path).name
            doc_url = self._abs_web(rel_path)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            blob = f"{titulo} {doc_url} NNSS planeamiento"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(f"{titulo} {rel_path}"),
                    "url": doc_url,
                    "page_url": self.planeamiento_url,
                    "blob": blob,
                    "origen": "web_planeamiento",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.formularios_url),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios e impresos — licencias y declaraciones responsables",
                "url": self.formularios_url,
                "source": "ayuntamiento",
                "nota": "Sin listado histórico de licencias concedidas; solo modelos de solicitud",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/board/"),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Santa Fe",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios de licencias y planeamiento publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "área urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo e Infraestructuras — Ayuntamiento de Santa Fe",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.planeamiento_url),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico municipal — NNSS 1998 y adaptación LOUA",
                "fecha": "2012-12-03",
                "tipo": "normas subsidiarias",
                "url": self.planeamiento_url,
                "source": "ayuntamiento",
                "origen": "nnss_pdf",
            },
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento aprobado — SituaDIFusión (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            },
            {
                "id": _stable_id("proy", VITUA_URL),
                "municipio": MUNICIPIO,
                "titulo": "VITUA — visor territorial y urbanístico de Andalucía",
                "fecha": None,
                "tipo": "planeamiento",
                "url": VITUA_URL,
                "source": "ayuntamiento",
                "origen": "vitua",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_BOARD_NON_URBAN.search(blob):
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                return False
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "ordenanza")):
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and re.search(r"(?i)informaci[oó]n p[uú]blica|consulta p[uú]blica", blob):
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
        if not RE_PROYECTO.search(urban_blob) and "planeamiento" not in proc and "ordenanza" not in proc:
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

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = item.get("blob") or item.get("titulo") or ""
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen", "web_planeamiento"),
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
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("web_", "sede_"))),
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
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for item in self._collect_planeamiento_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pdfs": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        def merge(rec: dict[str, Any] | None) -> None:
            if rec:
                existing[rec["id"]] = rec

        for rec in self._collect_proyecto_info_pages():
            merge(rec)
        for item in self._collect_planeamiento_pdfs():
            merge(self._pdf_to_proyecto(item))
        for item in self._collect_board():
            merge(self._board_to_proyecto(item))

        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}
