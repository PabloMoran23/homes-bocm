from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://jabugo.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://jabugo.es"
INFRAESTRUCTURA_URL = f"{WEB_BASE}/area-de-infraestructura/"
CITIZEN_URBANISMO_URL = f"{SEDE_BASE}/citizen-service/ff09163c-e59b-43c0-9540-e35e4a26c4c4"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Jabugo"
ID_PREFIX = "jabugo"

DEFAULT_SEED_PROYECTOS: list[dict[str, str]] = [
    {
        "url": "https://www.juntadeandalucia.es/boja/2023/227/65",
        "titulo": "PGOU Jabugo CP-045/2022 — subsanación, inscripción y publicación (BOJA 227/65)",
        "fecha": "2023-11-20",
        "tipo": "PGOU",
        "origen": "boja_pgou",
    },
    {
        "url": "https://www.juntadeandalucia.es/boja/2023/150/46",
        "titulo": "PGOU Jabugo CP-045/2022 — aprobación definitiva parcial (BOJA 150/46)",
        "fecha": "2023-08-02",
        "tipo": "PGOU",
        "origen": "boja_pgou",
    },
    {
        "url": SITUA_SEARCH,
        "titulo": "PGOU Jabugo — consulta SITUADIFusión (Junta de Andalucía)",
        "fecha": "2023-11-20",
        "tipo": "planeamiento",
        "origen": "situa",
    },
    {
        "url": INFRAESTRUCTURA_URL,
        "titulo": "Área de Infraestructuras, Urbanismo y Servicios Generales",
        "fecha": None,
        "tipo": "urbanismo",
        "origen": "web_area",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|terrazas|veladores)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normativa urban|cp-\d+/\d+)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|padrones|modificaci[oó]n.*presupuest|cr[eé]dito|"
    r"piscina|electores|baja oficio|cuenta general|boe n)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://jabugo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_FOLDER = re.compile(
    r'class="gIconLink exp"[^>]*>([^<]+)<span class="linkExtraInfo">\s*\(\s*(\d+)\s*\)</span>',
    re.I,
)
RE_CITIZEN_TRAMITE = re.compile(
    r'<span class="indentedItem\s*">([^<]+)</span>',
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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b or "normativa" in b:
        return "normativa urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b or "situa" in b:
        return "planeamiento"
    return "urbanismo"


class JabugoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress jabugo.es + sede espublico gestiona (tablón, transparencia, trámites urbanísticos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.citizen_urbanismo_url = str(
            self.config.get("citizen_urbanismo_url") or CITIZEN_URBANISMO_URL
        )
        self.infraestructura_url = str(
            self.config.get("infraestructura_url") or INFRAESTRUCTURA_URL
        )
        self.seed_proyectos = list(self.config.get("seed_proyectos") or DEFAULT_SEED_PROYECTOS)
        self.transparency_folders: list[dict[str, str]] = list(
            self.config.get("transparency_folders") or []
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-jabugo/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
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

    def _collect_transparency_folders(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for folder in self.transparency_folders:
            url = str(folder.get("url") or "").strip()
            titulo = str(folder.get("titulo") or "").strip()
            if not url or not titulo:
                continue
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                html = ""
            seen: set[str] = set()
            for m in re.finditer(
                r'href="((?:https://jabugo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
                r'[^>]*>([^<]+)',
                html,
                re.I,
            ):
                doc_url = m.group(1)
                if doc_url.startswith("/"):
                    doc_url = f"{self.sede_base}{doc_url}"
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                doc_title = _strip_html(m.group(2))
                combined = f"{titulo} — {doc_title}"
                if not RE_PROYECTO.search(combined):
                    continue
                rows.append(
                    {
                        "titulo": combined[:500],
                        "fecha": _fecha_from_blob(combined),
                        "url": doc_url,
                        "procedimiento": titulo,
                        "blob": combined,
                        "origen": "transparencia",
                    }
                )
            if not seen:
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "procedimiento": titulo,
                        "blob": titulo,
                        "origen": "transparencia",
                    }
                )

        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return rows

        for m in RE_TRANSPARENCY_FOLDER.finditer(html):
            title = _strip_html(m.group(1))
            count = m.group(2) or ""
            if not title or not RE_PROYECTO.search(title):
                continue
            combined = f"{title} ({count} documentos)" if count else title
            rows.append(
                {
                    "titulo": combined[:500],
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": title,
                    "blob": combined,
                    "origen": "transparencia_indice",
                }
            )
        return rows

    def _collect_seed_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for seed in self.seed_proyectos:
            titulo = str(seed.get("titulo") or "").strip()
            url = str(seed.get("url") or "").strip()
            if not titulo or not url:
                continue
            out.append(
                {
                    "titulo": titulo[:500],
                    "fecha": seed.get("fecha"),
                    "url": url,
                    "tipo": seed.get("tipo") or _proyecto_tipo(titulo),
                    "blob": titulo,
                    "origen": seed.get("origen") or "seed",
                }
            )
        return out

    def _collect_citizen_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.citizen_urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for label in RE_CITIZEN_TRAMITE.findall(html):
            titulo = _strip_html(label)
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": self.citizen_urbanismo_url,
                    "tipo": "trámite urbanismo",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
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
                "id": _stable_id("lic", self.citizen_urbanismo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanísticos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites urbanísticos — licencias y declaraciones responsables",
                "url": self.citizen_urbanismo_url,
                "source": "ayuntamiento",
                "nota": "DR obras, licencia urbanística, actividades, terrazas (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo de trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Gestión telemática de licencias (requiere identificación)",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
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

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("lic", titulo),
            "fecha_concesion": None,
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "sede_tramite",
        }

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row["url"]
        return {
            "id": _stable_id("proy", f"{row.get('origen')}:{url}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or titulo),
            "url": url,
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
        for item in self._collect_citizen_tramites():
            rec = self._tramite_to_licencia(item)
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
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_citizen_tramites():
            existing[self._tramite_to_licencia(item)["id"]] = self._tramite_to_licencia(item)
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

        for item in self._collect_seed_proyectos():
            add(self._generic_to_proyecto(item))
        for item in self._collect_transparency_folders():
            add(self._generic_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "seed": sum(1 for r in rows if str(r.get("origen", "")).startswith(("boja", "situa", "web", "seed"))),
            "transparencia": sum(1 for r in rows if "transparencia" in str(r.get("origen", ""))),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
