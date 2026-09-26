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

WEB_BASE = "https://www.lospalacios.org"
SEDE_BASE = "https://lospalacios.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "Los Palacios y Villafranca"
ID_PREFIX = "los-palacios-y-villafranca"
INE_CODE = "41091"

DIPUSEVILLA_LICENCIAS = (
    "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4106900F"
)
SITUA_URL = f"https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid={INE_CODE}"

URBANISMO_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/servicios/urbanismo/planeamientos-definitivos", "planeamiento definitivo"),
    (f"{WEB_BASE}/servicios/urbanismo/planeamientos-en-tramite", "planeamiento en trámite"),
    (f"{WEB_BASE}/servicios/urbanismo/convenios-definitivos", "convenio definitivo"),
    (f"{WEB_BASE}/servicios/urbanismo/convenios-en-tramite", "convenio en trámite"),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sus-|sus |ordenanza|delimitaci[oó]n|rehabilitaci[oó]n|"
    r"pemu|agr[oó]polis|gesti[oó]n|correcci[oó]n de errores|normas urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaciones presupuestarias|suplemento de cr[eé]dito|"
    r"deslinde camino|potestades administrativas)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://lospalacios\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    m = RE_FECHA_DMY_DASH.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "convenio" in blob and "gesti" in blob:
        return "convenio urbanístico"
    if "convenio" in blob and "planeam" in blob:
        return "convenio de planeamiento"
    if "plan parcial" in blob or re.search(r"\bsus[- ]?\d+", blob):
        return "plan parcial"
    if "plan especial" in blob or "pemu" in blob:
        return "plan especial"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "correcci" in blob and "pgou" in blob:
        return "corrección PGOU"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob or "normas urban" in blob:
        return "normativa urbanística"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class LosPalaciosYVillafrancaAyuntamientoAdapter(AyuntamientoAdapter):
    """ASP.NET MasterPorto (urbanismo tablas) + sede espublico gestiona (tablón/transparencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pgou_url = str(self.config.get("pgou_url") or f"{self.web_base}/servicios/urbanismo/pgou")
        self.urbanismo_pages = [
            tuple(x) for x in (self.config.get("urbanismo_pages") or URBANISMO_PAGES)
        ]
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
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

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-los-palacios-y-villafranca/1.0",
                ),
            },
        )
        if insecure is False:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

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

    def _parse_urbanismo_table(self, html: str, page_url: str, procedimiento: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.I | re.S)
            ]
            cells = [c for c in cells if c and c != "\xa0"]
            if len(cells) < 2:
                continue
            fecha = _parse_fecha_dmy(cells[0]) or _parse_fecha_dmy(" ".join(cells))
            titulo = cells[1] if _parse_fecha_dmy(cells[0]) else cells[-1]
            if not titulo or len(titulo) < 12:
                continue
            if not RE_PROYECTO.search(titulo) and "convenio" not in procedimiento:
                continue
            if titulo.lower() in ("objeto", "fecha del acuerdo o convenio", "documento"):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": page_url,
                    "procedimiento": procedimiento,
                    "blob": " ".join(cells),
                }
            )
        return rows

    def _collect_urbanismo_tables(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, procedimiento in self.urbanismo_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for item in self._parse_urbanismo_table(html, page_url, procedimiento):
                key = item["titulo"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows

    def _collect_pgou_links(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title or href in seen or href.startswith("#"):
                continue
            low = f"{title} {href}".lower()
            if not any(
                k in low
                for k in (
                    "pgou",
                    "norma",
                    "orden",
                    "modific",
                    "planeam",
                    "drive.google",
                )
            ):
                continue
            seen.add(href)
            url = _abs_url(href, self.web_base)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(title, url),
                    "url": url,
                    "procedimiento": "PGOU documentación",
                    "blob": title,
                }
            )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        if re.search(r"(?i)urbanismo.*obras", html):
            rows.append(
                {
                    "titulo": "Portal transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia",
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
                "id": _stable_id("lic", DIPUSEVILLA_LICENCIAS),
                "fecha_concesion": None,
                "tipo": "portal licencias Diputación de Sevilla",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta pública de licencias — Diputación de Sevilla (LicytalPub)",
                "url": DIPUSEVILLA_LICENCIAS,
                "source": "ayuntamiento",
                "nota": "Portal provincial LicytalPub CIF P4106900F",
                "origen": "dipusevilla",
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
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genérico")):
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "genérico" not in proc:
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

    def _web_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        titulo = row["titulo"]
        key = f"{origen}:{titulo}"
        return {
            "id": _stable_id("proy", key),
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "dipusevilla")
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
        for item in self._collect_urbanismo_tables():
            add(self._web_to_proyecto(item, "web_tabla"))
        for item in self._collect_pgou_links():
            add(self._web_to_proyecto(item, "web_pgou"))
        for item in self._collect_transparency_index():
            add(self._web_to_proyecto(item, "transparencia"))

        add(
            {
                "id": _stable_id("proy", SITUA_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Los Palacios y Villafranca — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_URL,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
