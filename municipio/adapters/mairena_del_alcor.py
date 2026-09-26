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

WEB_BASE = "https://www.mairenadelalcor.es"
SEDE_BASE = "https://mairenadelalcor.sedelectronica.es"
URBANISMO_SEDE = "https://urbanismomairenadelalcor.sedelectronica.es"
TRANSP_BASE = "https://transparencia.mairenadelalcor.es"
PGOM_BASE = "https://pgom.mairenadelalcor.net"

BOARD_URL = f"{SEDE_BASE}/board"
URBANISMO_BOARD_URL = f"{URBANISMO_SEDE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
PLANEAMIENTO_TRANSP_URL = (
    f"{TRANSP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "50.-Planeamiento-urbanistico-Planeamiento-General/"
)
PGOM_DOCS_URL = f"{PGOM_BASE}/category/documentacion/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
DIPUSEVILLA_LICENCIAS = (
    "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4105800E"
)

MUNICIPIO = "Mairena del Alcor"
ID_PREFIX = "mairena-del-alcor"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|calificaci[oó]n.*actividad|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|normas urban|ordenanza|nnss|cat[aá]logo|consulta p[uú]blica|avance|"
    r"delimitaci[oó]n|situa|vitua|ficha|calificaci[oó]n del suelo|adaptaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó]n municipal|baja de oficio|permiso de residencia|"
    r"proceso selectivo|polic[ií]a local|pleno extraordinario|convocatoria de el pleno|"
    r"cr[eé]ditos|subvenci[oó]n|empleo p[uú]blico|bop n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://(?:mairenadelalcor|urbanismomairenadelalcor)\.sedelectronica\.es)?'
    r"/preview-document/[a-f0-9-]+)\"",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_WP_PDF = re.compile(
    r'href="((?:https://pgom\.mairenadelalcor\.net)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "pgom" in blob or "plan general de ordenaci" in blob:
        return "PGOM"
    if "plan parcial" in blob or " pp " in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "licencia" in blob:
        return "licencia publicada"
    if "ficha" in blob:
        return "planeamiento"
    return "urbanismo"


class MairenaDelAlcorAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS + Dipusevilla transparencia + espublico sede (tablón) + PGOM WP."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_sede = str(self.config.get("urbanismo_sede") or URBANISMO_SEDE).rstrip("/")
        self.board_urls = [
            str(self.config.get("board_url") or BOARD_URL),
            str(self.config.get("urbanismo_board_url") or URBANISMO_BOARD_URL),
        ]
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.planeamiento_transp_url = str(
            self.config.get("planeamiento_transp_url") or PLANEAMIENTO_TRANSP_URL
        )
        self.pgom_base = str(self.config.get("pgom_base") or PGOM_BASE).rstrip("/")
        self.pgom_docs_url = str(self.config.get("pgom_docs_url") or PGOM_DOCS_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
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
                    "Mozilla/5.0 poc-bocm-mairena-del-alcor/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _collect_board(self, board_url: str, sede_base: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(board_url)
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
            url = preview_m.group(1) if preview_m else board_url
            if url.startswith("/"):
                url = f"{sede_base}{url}"

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

    def _collect_all_boards(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for board_url in self.board_urls:
            sede_base = self.urbanismo_sede if "urbanismomairenadelalcor" in board_url else self.sede_base
            for item in self._collect_board(board_url, sede_base):
                key = item.get("expediente") or item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.planeamiento_transp_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = m.group(1)
            pdf_url = _abs_url(href, self.transp_base)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
            titulo = f"{name} (transparencia planeamiento IND-50)"
            if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(pdf_url):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(name, pdf_url),
                    "url": pdf_url,
                    "procedimiento": "planeamiento transparencia",
                    "blob": f"{titulo} {pdf_url}",
                }
            )
        return rows

    def _collect_pgom_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        urls = [self.pgom_base, self.pgom_docs_url]
        for page_url in urls:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                pdf_url = _abs_url(m.group(1), self.pgom_base)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
                titulo = f"PGOM — {name}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name, pdf_url),
                        "url": pdf_url,
                        "procedimiento": "PGOM participación",
                        "blob": f"{titulo} {page_url}",
                    }
                )
            for m in re.finditer(
                r'href="(https://pgom\.mairenadelalcor\.net/[^"]+)"[^>]*>([^<]+)',
                html,
                re.I,
            ):
                link = m.group(1)
                title = _strip_html(m.group(2))
                if link in seen or len(title) < 8:
                    continue
                if not RE_PROYECTO.search(title) and "pgom" not in link.lower():
                    continue
                seen.add(link)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": None,
                        "url": link,
                        "procedimiento": "PGOM participación",
                        "blob": title,
                    }
                )

        rows.append(
            {
                "titulo": "Nuevo PGOM Mairena del Alcor — portal participación ciudadana",
                "fecha": "2024-01-01",
                "url": self.pgom_base,
                "procedimiento": "PGOM participación",
                "blob": "PGOM participación ciudadana fases redacción plan general",
            }
        )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        if RE_PROYECTO.search(html) or "URBANISMO" in html.upper():
            rows.append(
                {
                    "titulo": "Portal transparencia sede — Urbanismo, Obras Públicas y Medio Ambiente (638 docs)",
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": "transparencia urbanismo sede",
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", BOARD_URL),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Ayuntamiento de Mairena del Alcor",
                "url": BOARD_URL,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", URBANISMO_BOARD_URL),
                "fecha_concesion": None,
                "tipo": "tablón urbanismo y obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Urbanismo y Obras",
                "url": URBANISMO_BOARD_URL,
                "source": "ayuntamiento",
                "nota": "Sede dedicada urbanismo (urbanismomairenadelalcor.sedelectronica.es)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.urbanismo_sede}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede urbanismo",
                "url": f"{self.urbanismo_sede}/dossier",
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
                "nota": "Portal provincial CIF P4105800E",
                "origen": "dipusevilla",
            },
            {
                "id": _stable_id("lic", f"{self.urbanismo_sede}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede urbanismo)",
                "url": f"{self.urbanismo_sede}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        categoria = (row.get("categoria") or "").lower()
        if categoria == "urbanismo":
            return True
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
            if (row.get("categoria") or "").lower() != "urbanismo":
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

    def _doc_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("proy", f"{origen}:{row['url']}"),
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
        for item in self._collect_all_boards():
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
        for item in self._collect_all_boards():
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

        for item in self._collect_all_boards():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparencia_pdfs():
            add(self._doc_to_proyecto(item, "transparencia_ind50"))
        for item in self._collect_pgom_docs():
            add(self._doc_to_proyecto(item, "pgom"))
        for item in self._collect_transparency_index():
            add(self._doc_to_proyecto(item, "transparencia_sede"))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia_ind50": sum(1 for r in rows if r.get("origen") == "transparencia_ind50"),
            "pgom": sum(1 for r in rows if r.get("origen") == "pgom"),
            "transparencia_sede": sum(1 for r in rows if r.get("origen") == "transparencia_sede"),
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
