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

SEDE_BASE = "https://cartama.sedelectronica.es"
WEB_BASE = "https://www.cartama.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "Cártama"
ID_PREFIX = "cartama"

DEFAULT_WEB_SEED_PAGES: list[dict[str, str]] = [
    {
        "url": f"{WEB_BASE}/3918/urbanismo-planeamiento-y-gestion-urbanistica",
        "titulo": "Urbanismo. Planeamiento y Gestión urbanística",
        "tipo": "planeamiento",
    },
    {
        "url": f"{WEB_BASE}/4135/instrumentos-planeamiento-vigentes-tramitacion",
        "titulo": "Instrumentos de planeamiento vigentes en tramitación",
        "tipo": "planeamiento",
    },
    {
        "url": f"{WEB_BASE}/4136/innovaciones-plan-general",
        "titulo": "Innovaciones del Plan General",
        "tipo": "planeamiento",
    },
    {
        "url": f"{WEB_BASE}/4141/planes-parciales",
        "titulo": "Planes Parciales",
        "tipo": "plan parcial",
    },
    {
        "url": f"{WEB_BASE}/4140/planes-especiales",
        "titulo": "Planes Especiales",
        "tipo": "plan especial",
    },
    {
        "url": f"{WEB_BASE}/4135/estudios-detalle",
        "titulo": "Estudios de Detalle",
        "tipo": "estudio de detalle",
    },
    {
        "url": f"{WEB_BASE}/4139/otros-instrumentos-ordenacion-urbanistica-proyectos-actuacion",
        "titulo": "Otros Instrumentos de Ordenación Urbanística — Proyectos de Actuación",
        "tipo": "planeamiento",
    },
    {
        "url": f"{WEB_BASE}/11116/proyectos-urbanizacion-procedimiento",
        "titulo": "Proyectos de Urbanización — Procedimiento",
        "tipo": "proyecto de urbanización",
    },
    {
        "url": f"{WEB_BASE}/4134/estatutos-bases-actuacion-aprobacion-constitucion",
        "titulo": "Estatutos y Bases de Actuación y Aprobación de la Constitución de JC",
        "tipo": "gestión urbanística",
    },
    {
        "url": f"{WEB_BASE}/4142/reparcelacion-abreviada",
        "titulo": "Reparcelación Abreviada",
        "tipo": "reparcelación",
    },
    {
        "url": f"{WEB_BASE}/16271/plan-edil",
        "titulo": "Plan Edil",
        "tipo": "plan edil",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria|obra)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bopma|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n descriptiva|plan edil)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"auxiliar administrativo|empleo p[uú]blico|proceso selectivo|"
    r"cobranza iae|padrones?|padr[oó]n municipal|baja de oficio|"
    r"modificaci[oó]n presupuestaria|presupuesto|subvenci[oó]n|ayudas?|material escolar|"
    r"ordenanza fiscal|icio|tesorer[ií]a|gesti[oó]n de tesorer)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://cartama\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PAGE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_OG_PUBLISHED = re.compile(
    r'<meta\s+property="article:published_time"\s+content="(\d{2}/\d{2}/\d{4})',
    re.I,
)


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_page_title(title: str) -> str:
    t = unescape(title or "").strip()
    t = re.sub(r"\s*-\s*Ayuntamiento de C[aá]rtama\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*-\s*Ayuntamiento de C.rtama\s*$", "", t, flags=re.I)
    return t[:500]


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or "planes parciales" in n:
        return "plan parcial"
    if "plan especial" in n or "planes especiales" in n:
        return "plan especial"
    if "innovaci" in n or "pgou" in n or "instrumento" in n:
        return "planeamiento"
    if "estudio de detalle" in n or "estudios de detalle" in n:
        return "estudio de detalle"
    if "reparcel" in n:
        return "reparcelación"
    if "urbanizaci" in n:
        return "proyecto de urbanización"
    if "plan edil" in n:
        return "plan edil"
    if "estatuto" in n or "junta de compensaci" in n:
        return "gestión urbanística"
    if "urbanismo" in n or "planeamiento" in n:
        return "planeamiento"
    return "planeamiento"


class CartamaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + web Diputación Málaga (procedimientos planeamiento)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_seed_pages = list(self.config.get("web_seed_pages") or DEFAULT_WEB_SEED_PAGES)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, web: bool = False) -> str:
        time.sleep(self.delay_s)
        ua = self.config.get("web_user_agent" if web else "user_agent", "poc-bocm-cartama/1.0")
        req = urllib.request.Request(url, headers={"User-Agent": ua})
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

    def _collect_web_procedimientos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.web_seed_pages:
            if isinstance(item, str):
                url = item
                titulo = ""
                tipo = "planeamiento"
            else:
                url = str(item.get("url") or "")
                titulo = str(item.get("titulo") or "")
                tipo = str(item.get("tipo") or "planeamiento")
            if not url:
                continue

            fecha: str | None = None
            try:
                html = self._fetch(url, web=True)
                title_m = RE_PAGE_TITLE.search(html)
                if title_m:
                    fetched = _clean_page_title(title_m.group(1))
                    if fetched:
                        titulo = fetched
                pub_m = RE_OG_PUBLISHED.search(html)
                if pub_m:
                    fecha = _parse_fecha_dmy(pub_m.group(1))
            except urllib.error.URLError:
                pass

            if not titulo:
                titulo = url.rsplit("/", 1)[-1].replace("-", " ").title()

            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": tipo if tipo != "planeamiento" else _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "web_planeamiento",
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
                "id": _stable_id("lic", f"{self.sede_base}/transparency"),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                "url": f"{self.sede_base}/transparency",
                "source": "ayuntamiento",
                "nota": "Categoría 8 URBANISMO (~935 documentos); navegación Wicket AJAX",
                "origen": "sede_transparencia",
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
                "nota": "Requiere identificación Cl@ve; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()

        if RE_BOARD_NON_URBAN.search(blob):
            if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
                pass
            elif RE_LICENCIA.search(blob) or re.search(
                r"(?i)(planeam|pgou|informaci[oó]n p[uú]blica|reparcel|bopma|plan (?:parcial|especial))",
                blob,
            ):
                pass
            else:
                return False

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

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento general|aprobaci[oó]n inicial", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)cambio de uso|sector", blob):
            tipo = "modificación planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)rectificaci[oó]n descriptiva", blob):
            tipo = "rectificación catastral"

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
            "info": sum(1 for r in rows if r.get("origen", "").startswith("sede_")),
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
        for rec in self._collect_web_procedimientos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
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
