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

SEDE_BASE = "https://ubrique.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
TRANSPARENCIA_BASE = "https://transparencia.ayuntamientoubrique.es"
DOCS_BASE = "http://transparenciaubrique.es/documentos"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Ubrique"
ID_PREFIX = "ubrique"

DEFAULT_TRANSPARENCY_FOLDERS: list[str] = [
    f"{SEDE_BASE}/transparency/d3a2fa91-8739-4f7d-85b9-63e798672352/",
    f"{SEDE_BASE}/transparency/22390146-92f7-45cc-ae9b-750cf0d2ac0c/",
    f"{SEDE_BASE}/transparency/684a418d-29ea-422d-86d2-8b5902915d4e/",
]

DEFAULT_WP_PAGES: list[str] = [
    f"{TRANSPARENCIA_BASE}/pgou-ubrique-documento-de-aprobacion-provisional/",
    f"{TRANSPARENCIA_BASE}/plan-general-de-ordenacion-urbanistica-pgou/",
    f"{TRANSPARENCIA_BASE}/licencias-de-obras/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|certificado final de obras|"
    r"procedimiento para ejecuci[oó]n de obras)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|ambiental estrat[eé]gico)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normas urban|rectificaci[oó]n.*finca|movilidad urbana|"
    r"estructura (?:territorial|urbana)|hidrolog|vivienda|situa|dae|eae|"
    r"certificado t[eé]cnico|adaptaci[oó]n del local|instalaciones)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|herederos ab intestato|feria y fiestas|"
    r"junta de gobierno|adjudicaci[oó]n.*caseta|contrataciones)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW = re.compile(
    r'href="((?:https://ubrique\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
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
    m = re.search(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
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
    if "plan de movilidad" in b or "pmus" in b:
        return "plan movilidad urbana"
    if "normas urban" in b:
        return "normativa urbanística"
    if "estudio ambiental" in b or "eae" in b:
        return "evaluación ambiental"
    if "memoria" in b and "ordenaci" in b:
        return "memoria planeamiento"
    if "planos" in b:
        return "cartografía urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "rectificaci" in b and "finca" in b:
        return "rectificación catastral"
    if "certificado t" in b and "actividad" in b:
        return "certificado actividad"
    if "licencia" in b:
        return "licencia publicada"
    if "proyecto t" in b or re.search(r"\bproyecto\b", b):
        return "proyecto técnico"
    if "situa" in b:
        return "planeamiento"
    return "urbanismo"


class UbriqueAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + WordPress transparencia (PGOU/licencias) + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.docs_base = str(self.config.get("docs_base") or DOCS_BASE).rstrip("/")
        self.transparency_folders = [
            str(u) for u in (self.config.get("transparency_folders") or DEFAULT_TRANSPARENCY_FOLDERS)
        ]
        self.wp_seed_pages = [str(u) for u in (self.config.get("wp_seed_pages") or DEFAULT_WP_PAGES)]
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", False):
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ubrique/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href.replace("&amp;", "&")).strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.sede_base)}/", href)

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

            preview_m = RE_PREVIEW.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_url(url)

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
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_transparency_folder(self, folder_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(folder_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            row_html = m.group(1)
            preview_m = RE_PREVIEW.search(row_html)
            if not preview_m:
                continue
            url = self._abs_url(preview_m.group(1))
            if url in seen:
                continue
            seen.add(url)

            title_m = re.search(r'title="([^"]+)"', row_html)
            anchor_m = re.search(r'class="gIconLink"[^>]*>([^<]+)</a>', row_html, re.I)
            titulo = ""
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            elif anchor_m:
                titulo = _strip_html(anchor_m.group(1))
            if not titulo:
                titulo = url.rsplit("/", 1)[-1]

            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "blob": f"{titulo} {folder_url}",
                    "origen": "transparencia_sede",
                    "folder": folder_url,
                }
            )

        if not rows:
            for m in RE_PREVIEW.finditer(html):
                url = self._abs_url(m.group(1))
                if url in seen:
                    continue
                seen.add(url)
                local = html[max(0, m.start() - 500) : m.end() + 200]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                anchor_m = re.search(r'class="gIconLink"[^>]*>([^<]+)</a>', local, re.I)
                titulo = ""
                if title_m and title_m.group(1).strip():
                    titulo = title_m.group(1).strip()
                elif anchor_m:
                    titulo = _strip_html(anchor_m.group(1))
                else:
                    titulo = url.rsplit("/", 1)[-1]
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "blob": f"{titulo} {folder_url}",
                        "origen": "transparencia_sede",
                        "folder": folder_url,
                    }
                )
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.wp_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = ""
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            if h1:
                page_title = _strip_html(h1.group(1))

            for href, inner in RE_LINK.findall(html):
                anchor = _strip_html(inner)
                if not anchor or len(anchor) < 4:
                    continue
                low = href.lower()
                if not any(x in low for x in (".pdf", ".rar", ".zip", "documentos/", "transparency/")):
                    if "pgou" not in anchor.lower() and "licencia" not in anchor.lower():
                        continue
                url = self._abs_url(href, page_url)
                if url in seen:
                    continue
                seen.add(url)
                titulo = anchor[:500]
                if page_title and page_title.lower() not in titulo.lower():
                    titulo = f"{page_title} — {anchor}"[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(f"{titulo} {url}"),
                        "url": url,
                        "blob": f"{titulo} {url} {page_title}",
                        "origen": "transparencia_wp",
                        "page": page_url,
                    }
                )

        rows.append(
            {
                "titulo": "Planeamiento urbanístico — SITUA Junta de Andalucía",
                "fecha": None,
                "url": self.situa_url,
                "blob": f"SITUA planeamiento Ubrique {self.situa_url}",
                "origen": "situa",
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
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.transparencia_base}/licencias-de-obras/"),
                "fecha_concesion": None,
                "tipo": "procedimientos licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de obras — procedimientos y formularios",
                "url": f"{self.transparencia_base}/licencias-de-obras/",
                "source": "ayuntamiento",
                "nota": "Declaración responsable, licencia ordinaria y comunicación previa (PDF informativos)",
                "origen": "transparencia_wp",
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
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de licencias concedidas",
                "origen": "sede_tramite",
            },
        ]

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

    def _is_proyecto_blob(self, blob: str) -> bool:
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob))

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
        if not self._is_proyecto_blob(blob):
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

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_proyecto_blob(blob):
            return None
        key = row.get("url") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "transparencia"),
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia_wp")
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
        for folder_url in self.transparency_folders:
            for item in self._collect_transparency_folder(folder_url):
                add(self._generic_to_proyecto(item))
        for item in self._collect_wp_pages():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia_sede": sum(1 for r in rows if r.get("origen") == "transparencia_sede"),
            "transparencia_wp": sum(1 for r in rows if r.get("origen") == "transparencia_wp"),
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
