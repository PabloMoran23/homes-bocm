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

SEDE_BASE = "https://castellardelafrontera.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://www.castellardelafrontera.es"
ORDENANZAS_URL = f"{WEB_BASE}/ayuntamiento/ordenanzas"
PBOM_URL = (
    "https://www.dipucadiz.es/asistencia-a-municipios/asistencia-tecnica/"
    "planeamiento-urbanistico/ayuntamientos/castellar/pbom/"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
TRANSPARENCY_DIP_URL = (
    "https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?"
    "p_p_id=indicadorespublicosv2_WAR_gestionindicadorestransparenciav2portlet&"
    "p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&"
    "p_p_col_pos=2&p_p_col_count=4&"
    "_indicadorespublicosv2_WAR_gestionindicadorestransparenciav2portlet_seccionId=__SECCION__&"
    "_indicadorespublicosv2_WAR_gestionindicadorestransparenciav2portlet_entidadId=403"
)
MUNICIPIO = "Castellar de la Frontera"
ID_PREFIX = "castellar-de-la-frontera"

DEFAULT_ORDENANZAS_PAGES: list[str] = [
    ORDENANZAS_URL,
    f"{WEB_BASE}/ayuntamiento/ordenanzas/14-ordenanzas-municipales",
    f"{WEB_BASE}/ayuntamiento/ordenanzas/15-ordenanzas-fiscales",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pbom|nn\.?ss|normas subsidiarias|"
    r"convenio|informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|boja|bopcadiz|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|expropiaci[oó]n|avance|delimitaci[oó]n|situa|"
    r"documento de alcance|declaraci[oó]n ambiental|participaci[oó]n ciudadana)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|subvencion|pleno|convocatoria de el pleno|"
    r"orden del d[ií]a|listado definitivo personal)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://castellardelafrontera\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_PBOM_PDF = re.compile(
    r'href="((?:https://www\.dipucadiz\.es)?/export/sites/default/[^"]+\.pdf[^"]*)"',
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
    b = blob.lower()
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "nn.ss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "documento de alcance" in b or "dae" in b:
        return "estudio ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "cartograf" in b or "hoja_" in b:
        return "cartografía urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b:
        return "planeamiento"
    return "urbanismo"


class CastellarDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón) + web Joomla + PBOM Diputación Cádiz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.pbom_url = str(self.config.get("pbom_url") or PBOM_URL)
        self.ordenanzas_pages = [
            str(u) for u in (self.config.get("ordenanzas_pages") or DEFAULT_ORDENANZAS_PAGES)
        ]
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency/"
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
                    "Mozilla/5.0 poc-bocm-castellar-de-la-frontera/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.web_base)}/", href)

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

    def _collect_pbom(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, tipo: str = "PBOM", fecha: str | None = None) -> None:
            abs_url = self._abs_url(url, "https://www.dipucadiz.es")
            if abs_url in seen:
                return
            seen.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": titulo[:500],
                    "tipo": tipo,
                    "fecha": fecha,
                    "blob": f"{titulo} PBOM Castellar planeamiento",
                    "origen": "dipucadiz_pbom",
                }
            )

        add(self.pbom_url, "Plan Básico de Ordenación Municipal (PBOM) — Castellar de la Frontera", "PBOM")
        add(SITUA_SEARCH, "Planeamiento vigente (NN.SS.) — consulta SITU@ Junta de Andalucía", "normas subsidiarias")

        try:
            html = self._fetch(self.pbom_url)
        except urllib.error.URLError:
            return rows

        for m in RE_PBOM_PDF.finditer(html):
            href = m.group(1)
            if "castellar/pbom" not in href.lower():
                continue
            name = Path(urllib.parse.unquote(href.split("?")[0])).stem.replace("_", " ")
            add(href, f"PBOM Castellar — {name}", _proyecto_tipo(name))

        return rows

    def _collect_ordenanzas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.ordenanzas_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if not anchor or len(anchor) < 6:
                    continue
                doc_url = self._abs_url(href, page_url)
                if doc_url in seen:
                    continue
                is_doc = bool(re.search(r"(?i)\.(pdf|zip)(?:\?|$)", doc_url)) or "/images/" in doc_url
                if not is_doc and "ordenanza" not in anchor.lower():
                    continue
                blob = f"{anchor} {doc_url}"
                if not RE_PROYECTO.search(blob) and "ordenanza" not in anchor.lower():
                    continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": anchor[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": doc_url,
                        "blob": blob,
                        "origen": "web_ordenanzas",
                    }
                )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        if "URBANISMO" in html:
            rows.append(
                {
                    "titulo": "Portal transparencia sede — Urbanismo, Obras Públicas y Medio Ambiente (88 docs)",
                    "fecha": None,
                    "url": self.transparency_url,
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia sede",
                    "origen": "transparencia_sede",
                }
            )
        rows.append(
            {
                "titulo": "Catálogo transparencia Diputación Cádiz — Ayuntamiento Castellar de la Frontera",
                "fecha": None,
                "url": TRANSPARENCY_DIP_URL,
                "blob": "transparencia dipucadiz castellar urbanismo",
                "origen": "transparencia_dip",
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
        if not RE_PROYECTO.search(blob) and "licencias urban" not in proc:
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

    def _meta_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "pbom"),
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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
        for item in self._collect_pbom():
            add(self._meta_to_proyecto(item))
        for item in self._collect_ordenanzas():
            blob = item.get("blob") or ""
            if RE_PROYECTO.search(blob):
                add(self._meta_to_proyecto({**item, "tipo": _proyecto_tipo(blob)}))
        for item in self._collect_transparency_index():
            add(self._meta_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pbom": sum(1 for r in rows if r.get("origen") == "dipucadiz_pbom"),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "web_ordenanzas"),
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
