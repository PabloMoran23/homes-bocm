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

SEDE_BASE = "https://pealdebecerro.sedelectronica.es"
WEB_BASE = "https://www.pealdebecerro.es"
BOARD_URL = f"{SEDE_BASE}/board/"
URBANISMO_URL = f"{WEB_BASE}/ayuntamiento/urbanismo/"
CITIZEN_URBANISMO_URL = (
    f"{SEDE_BASE}/citizen-service/f30306de-0ffc-415f-9820-6802cd4aad98"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Peal de Becerro"
ID_PREFIX = "peal-de-becerro"

DEFAULT_PLANEAMIENTO_SEEDS: list[dict[str, Any]] = [
    {
        "titulo": (
            "Modificación NNSS — Delimitación S.U. polígono industrial "
            "y 6 modificaciones más (aprobación definitiva)"
        ),
        "url": "https://www.juntadeandalucia.es/boja/2024/93/58",
        "fecha": "2024-05-15",
        "tipo": "modificación planeamiento",
        "expte": "1-211/04",
        "origen": "boja_publicacion",
    },
    {
        "titulo": (
            "Normas Subsidiarias de Planeamiento Municipal (NNSS 1997) — "
            "instrumento vigente"
        ),
        "url": SITUA_SEARCH,
        "fecha": "1997-01-01",
        "tipo": "NNSS",
        "expte": None,
        "origen": "situa",
        "nota": "Consulta SITUADIFUSION Junta de Andalucía (INE 23066)",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|bando.*(?:solar|terreno)|"
    r"normativa urban|eae|evaluaci[oó]n ambiental|vivienda protegida|equipamiento)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n.*presupuest|cr[eé]dito extraordinario|"
    r"jurado|fiestas locales|mercadillo|mercado semanal|subvenci[oó]n|licitaci[oó]n|"
    r"bolsa de empleo|padr[oó]n econ[oó]mico|activa-t joven|plan provincial|"
    r"cambio clim[aá]tico|escuela municipal|deportes|barra bar|fiesta de las mercedes)",
)
RE_BOARD_URBAN_STRONG = re.compile(
    r"(?i)(urban|planeam|licencia|obra|pgou|pbom|nnss|suelo|sector|reparcel|"
    r"normativa urban|pol[ií]gono industrial|equipamiento|modificaci[oó]n.*(?:nnss|pgou|planeam)|"
    r"informaci[oó]n p[uú]blica.*(?:urban|planeam|suelo))",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://pealdebecerro\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
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
    if "nnss" in b or "normas subsidiarias" in b:
        return "NNSS"
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and ("puntual" in b or "pgou" in b or "pbom" in b or "nnss" in b):
        return "modificación planeamiento"
    if "plan parcial" in b or "sector" in b or "polígono" in b or "poligono" in b:
        return "plan parcial"
    if "reparcel" in b:
        return "reparcelación"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class PealDeBecerroAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress DipuJaén (Colibri) + sede espublico gestiona (tablón, transparencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.citizen_urbanismo_url = str(
            self.config.get("citizen_urbanismo_url") or CITIZEN_URBANISMO_URL
        )
        self.planeamiento_seeds = list(
            self.config.get("planeamiento_seeds") or DEFAULT_PLANEAMIENTO_SEEDS
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
                "User-Agent": self.config.get("user_agent", "poc-bocm-peal-de-becerro/1.0")
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

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

    def _collect_planeamiento_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.planeamiento_seeds:
            url = str(seed["url"])
            titulo = str(seed["titulo"])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": seed.get("fecha"),
                "tipo": seed.get("tipo") or _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "expte": seed.get("expte"),
                "origen": seed.get("origen") or "planeamiento_seed",
            }
            if seed.get("nota"):
                rec["nota"] = seed["nota"]
            rows.append(rec)
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
                "nota": "Bandos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.citizen_urbanismo_url),
                "fecha_concesion": None,
                "tipo": "información licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Obras y Urbanismo — DR, licencias y comunicaciones previas",
                "url": self.citizen_urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Página informativa transparencia sede (espublico)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "sección urbanismo web municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — web municipal (Colibri/DipuJaén)",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Listado dinámico vacío; trámites vía sede electrónica",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/citaprevia"),
                "fecha_concesion": None,
                "tipo": "cita previa",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Cita previa — sede electrónica",
                "url": f"{self.sede_base}/citaprevia",
                "source": "ayuntamiento",
                "nota": "Atención presencial urbanismo vía sede",
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
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_BOARD_URBAN_STRONG.search(blob):
            return None
        if not RE_BOARD_URBAN_STRONG.search(blob):
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
            "info": sum(1 for r in rows if r.get("origen") != "tablon"),
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
        for item in self._collect_planeamiento_seeds():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "planeamiento_seed": sum(
                1 for r in rows if r.get("origen") in ("planeamiento_seed", "boja_publicacion", "situa")
            ),
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
