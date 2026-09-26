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

SEDE_BASE = "https://finestrat.sedelectronica.es"
WEB_BASE = "https://ayto-finestrat.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
MUNICIPIO = "Finestrat"
ID_PREFIX = "finestrat"
COD_INE_MUN = "03054"

GVA_PLANEAMIENTO_URL = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03054%20FINESTRAT"
)

DEFAULT_SEED_PROYECTOS: list[dict[str, Any]] = [
    {
        "titulo": "Normas Subsidiarias de Planeamiento (1989 y modificaciones)",
        "url": f"{WEB_BASE}/areas-y-servicios/urbanismo/",
        "fecha": "1989-01-01",
        "tipo": "normas subsidiarias",
        "origen": "web_urbanismo",
    },
    {
        "titulo": "Modificación Plan Parcial PP-5 AD — septiembre 2014",
        "url": f"{WEB_BASE}/download/planos-ordenacion/",
        "fecha": "2014-09-01",
        "tipo": "plan parcial",
        "origen": "web_planos",
    },
    {
        "titulo": "Documento Consultivo — Plan General Estructural Finestrat",
        "url": f"{WEB_BASE}/areas-y-servicios/urbanismo/",
        "fecha": "2025-11-01",
        "tipo": "consulta pública",
        "origen": "pge_consulta",
    },
    {
        "titulo": "Planos de ordenación — documentación consultiva PP-5",
        "url": f"{WEB_BASE}/download/planos-ordenacion/",
        "fecha": "2017-06-15",
        "tipo": "plan parcial",
        "origen": "web_planos",
    },
    {
        "titulo": "Registro de planeamiento GVA — Finestrat (INE 03054)",
        "url": GVA_PLANEAMIENTO_URL,
        "fecha": None,
        "tipo": "planeamiento",
        "origen": "gva_registro",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estructural)|pgou|pge|pp[\-\s]*\d|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"normas subsidiarias|consulta p[uú]blica|documento consultivo)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|padrones|baja en el pmh|pmh\b|boe\b|bop\b|"
    r"empleo p[uú]blico|matrimonio|delegaci[oó]n de funciones)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://finestrat\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan general estructural" in n or "pge" in n:
        return "plan general estructural"
    if "plan parcial" in n or re.search(r"pp[\-\s]*\d", n):
        return "plan parcial"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "consulta p" in n and "blica" in n or "documento consultivo" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "licencia" in n:
        return "licencia publicada"
    return "planeamiento"


class FinestratAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón + transparencia) + web ayto-finestrat.es (seeds estáticos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.seed_proyectos = list(self.config.get("seed_proyectos") or DEFAULT_SEED_PROYECTOS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-finestrat/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.sede_base}/", href.lstrip("/"))

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
            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()

            expediente = cells.get("class_folderCode", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "categoria": cells.get("class_boardCategory", "")[:120],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {cells.get('class_folderName', '')} "
                        f"{cells.get('class_boardCategory', '')} "
                        f"{cells.get('class_description', '')} "
                        f"{title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        if re.search(r"URBANISME|URBANISMO", html, re.I):
            rows.append(
                {
                    "titulo": (
                        "Portal transparencia — Urbanismo, Obras Públicas y Medio Ambiente (162 docs)"
                    ),
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia",
                }
            )

        seen: set[str] = set()
        for m in re.finditer(
            r'href="((?:https://finestrat\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
            r'[^>]*>([^<]+)',
            html,
            re.I,
        ):
            doc_url = self._abs_sede(m.group(1))
            if doc_url in seen:
                continue
            seen.add(doc_url)
            doc_title = _strip_html(m.group(2))
            if not doc_title or len(doc_title) < 4:
                continue
            if not RE_PROYECTO.search(doc_title):
                continue
            rows.append(
                {
                    "titulo": doc_title[:500],
                    "fecha": _fecha_from_blob(doc_title),
                    "url": doc_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": doc_title,
                }
            )
        return rows

    def _collect_seed_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.seed_proyectos:
            titulo = str(item.get("titulo") or "").strip()
            url = str(item.get("url") or self.web_base).strip()
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": item.get("fecha"),
                    "url": url,
                    "procedimiento": str(item.get("origen") or "seed"),
                    "blob": titulo,
                    "origen": str(item.get("origen") or "seed"),
                    "tipo": item.get("tipo"),
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
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
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
            {
                "id": _stable_id("lic", f"{self.web_base}/areas-y-servicios/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (web municipal)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — licencias, parcelaciones y disciplina urbanística",
                "url": f"{self.web_base}/areas-y-servicios/urbanismo/",
                "source": "ayuntamiento",
                "nota": "Información de trámites; cita previa 965 878 100",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo" or any(k in proc for k in ("planeamiento", "licencia", "urban", "obra")):
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
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        origen = row.get("origen") or "seed"
        return {
            "id": _stable_id("proy", f"{origen}:{titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": origen,
        }

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("proy", f"transparency:{titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
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
        for item in self._collect_seed_proyectos():
            add(self._seed_to_proyecto(item))
        for item in self._collect_transparency_index():
            add(self._transparency_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "seed": sum(1 for r in rows if str(r.get("origen", "")).startswith(("web_", "gva_", "pge_", "seed"))),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        def add(rec: dict[str, Any] | None) -> None:
            if rec:
                existing[rec["id"]] = rec

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_proyectos():
            add(self._seed_to_proyecto(item))
        for item in self._collect_transparency_index():
            add(self._transparency_to_proyecto(item))

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
