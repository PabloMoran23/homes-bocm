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
from municipio.geometry import record_geometry

SEDE_BASE = "https://estepona.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCIA_WP = (
    "https://transparencia.estepona.es/visual/informacion-urbanistica-y-territorial/"
)
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29051"
SITES_VISOR_URL = "https://sites.estepona.es/VisorWebGIS/#/SITEstepona"
MUNICIPIO = "Estepona"
ID_PREFIX = "estepona"

TRANSPARENCY_SECTIONS: list[tuple[str, str]] = [
    ("Planes de ordenación urbana", "91db2349-8f7e-47b7-a429-81192079f13a"),
    ("Planeamiento, gestión y licencias", "5fdc2c2e-76a5-4c12-8274-2f5dcb7550bc"),
    ("Anuncios y licitaciones de obras públicas", "5d99b758-a4ca-471e-923c-cb21de03b912"),
    (
        "Información sobre concurrentes, ofertas y resoluciones",
        "cef97dae-4814-4e84-85a5-a5f79ac792a3",
    ),
    (
        "Seguimiento y control de la ejecución de obras",
        "913cd0ca-5f1b-416a-9195-c172bbf023bc",
    ),
    (
        "Indicadores sobre urbanismo y obras públicas",
        "37244e15-dfb9-49ad-ae5b-a643a332e0db",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|calificaci[oó]n ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|actuaci[oó]n|desarrollo|vivienda unifamiliar|"
    r"pol[ií]gono|cortijo|finca)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"liquidaci[oó]n|elecciones|fiestas|halloween|pleno|junta de gobierno|"
    r"subvenci[oó]n|empleo p[uú]blico|test\.|tribunal)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://estepona\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_FOLDER = re.compile(
    r'class="gIconLink exp"[^>]*>(.*?)(?:<span class="linkExtraInfo">|$)',
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


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "planeamiento de desarrollo" in blob or "actuaci" in blob:
        return "proyecto de actuación"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "calificaci" in blob and "ambiental" in blob:
        return "calificación ambiental"
    if "licencia" in blob:
        return "licencia publicada"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "obra p" in blob and "blica" in blob:
        return "obra pública"
    return "urbanismo"


class EsteponaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón + transparencia) + SITUA + visor SITES."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparencia_wp = str(self.config.get("transparencia_wp_url") or TRANSPARENCIA_WP)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.sites_visor_url = str(self.config.get("sites_visor_url") or SITES_VISOR_URL)
        self.transparency_sections = [
            tuple(x) for x in (self.config.get("transparency_sections") or TRANSPARENCY_SECTIONS)
        ]
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-estepona/1.0")},
        )
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

    def _collect_transparency_folders(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for section_title, section_uuid in self.transparency_sections:
            section_url = f"{self.sede_base}/transparency/{section_uuid}/"
            try:
                html = self._fetch(section_url)
            except urllib.error.URLError:
                continue
            for m in RE_TRANSPARENCY_FOLDER.finditer(html):
                folder_title = _strip_html(m.group(1))
                if not folder_title or len(folder_title) < 12:
                    continue
                if folder_title.startswith("1. Tiene una sección visible"):
                    continue
                titulo = f"{section_title} — {folder_title}"[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(folder_title),
                        "url": section_url,
                        "procedimiento": section_title,
                        "blob": f"{section_title} {folder_title}",
                        "origen": "transparencia_sede",
                        "section_uuid": section_uuid,
                    }
                )
        return rows

    def _collect_seed_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.situa_url),
                "municipio": MUNICIPIO,
                "titulo": "SITUA — planeamiento urbanístico digitalizado (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.situa_url,
                "source": "ayuntamiento",
                "origen": "situa",
            },
            {
                "id": _stable_id("proy", self.sites_visor_url),
                "municipio": MUNICIPIO,
                "titulo": "SITES — visor GIS planeamiento y callejero municipal",
                "fecha": None,
                "tipo": "visor urbanístico",
                "url": self.sites_visor_url,
                "source": "ayuntamiento",
                "origen": "sites_visor",
            },
            {
                "id": _stable_id("proy", self.transparencia_wp),
                "municipio": MUNICIPIO,
                "titulo": "Portal transparencia — información urbanística y territorial",
                "fecha": None,
                "tipo": "transparencia",
                "url": self.transparencia_wp,
                "source": "ayuntamiento",
                "origen": "transparencia_wp",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y planeamiento",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — declaraciones responsables y licencias",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Trámites urbanísticos sin listado histórico público de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transparencia_wp),
                "fecha_concesion": None,
                "tipo": "transparencia planeamiento y licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Transparencia — planeamiento, gestión y licencias",
                "url": self.transparencia_wp,
                "source": "ayuntamiento",
                "nota": "Indicadores y documentación en portal transparencia + sede",
                "origen": "transparencia_wp",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(
            k in proc
            for k in (
                "planeamiento",
                "licencia",
                "urban",
                "actividad",
                "obra",
                "desarrollo",
                "ocupaci",
                "calificaci",
            )
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
        elif re.search(r"(?i)obra|urban", blob):
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "desarrollo" not in proc:
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

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        return {
            "id": _stable_id("proy", f"transparency:{row.get('section_uuid')}:{title}"),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(title, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia_sede",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia_wp")),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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

        for rec in self._collect_seed_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency_folders():
            add(self._transparency_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_sede"),
            "seeds": sum(1 for r in rows if r.get("origen") in ("situa", "sites_visor", "transparencia_wp")),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
