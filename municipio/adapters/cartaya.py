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

DRUPAL_BASE = "https://www.cartaya.es"
SEDE_BASE = "https://cartaya.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
AGENDA_URBANA_PDF = f"{DRUPAL_BASE}/sites/default/files/documentos/agendaurbanacartaya.pdf"
MUNICIPIO = "Cartaya"
ID_PREFIX = "cartaya"

DEFAULT_SEED_PAGES: list[str] = [
    f"{DRUPAL_BASE}/es/normativa/instrumentos-urbanisticos",
    "http://cartaya.es/areas-municipales?area=urbanismo",
    f"{DRUPAL_BASE}/es/areas-municipales/agenda-urbana",
    f"{DRUPAL_BASE}/es/areas-municipales/noticias/urbanismo",
    f"{DRUPAL_BASE}/es/tablon-de-anuncios",
    f"{DRUPAL_BASE}/es/tramites/descarga-de-documentos",
    f"{DRUPAL_BASE}/es/normativa",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|cesi[oó]n administrativa)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de actuaci[oó]n)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|unidad de ejecuci[oó]n|"
    r"instrumento|normativa urban|agenda urbana|tracto registral|autocaravan|"
    r"bonificaci[oó]n.*vivienda|habilitar.*[áa]rea)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n de cr[eé]dito|bolsa de empleo|"
    r"monitor (?:deport|actividad)|polic[ií]a local|t[eé]cnico|junta local de protecci[oó]n civil|"
    r"listado (?:provisional|definitivo).*admitid)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(revista|fiestas|empleo|deporte|turismo|bandera verde|whatsapp|"
    r"residuos vegetales|podas|politica de calidad)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://)?(?:www\.)?cartaya\.es)?/sites/[^"\']+\.pdf[^"\']*["\']',
    re.I,
)
RE_NODE_HREF = re.compile(
    r'href=["\']((?:https://(?:www\.)?cartaya\.es)?/es/node/(\d+))["\']',
    re.I,
)
RE_NEWS_HREF = re.compile(
    r'href=["\']((?:https://(?:www\.)?cartaya\.es)?/es/noticias/[^"\']+)["\']',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://cartaya\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_NEWS_DATE = re.compile(r'class="date-display-single"[^>]*content="(\d{4}-\d{2}-\d{2})"')


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


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("%20", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "agenda urbana" in b:
        return "agenda urbana"
    if "plan de actuaci" in b:
        return "plan de actuación integrado"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "plan especial" in b or " pe " in b:
        return "plan especial"
    if "pgou" in b or "plan general" in b or "modificaci" in b:
        return "PGOU"
    if "unidad de ejecuci" in b or " ue" in b:
        return "unidad de ejecución"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "tracto registral" in b:
        return "disposición normativa"
    if "autocaravan" in b:
        return "planeamiento"
    if "bonificaci" in b and "vivienda" in b:
        return "ordenanza fiscal urbanística"
    if "normativa" in b or "ordenanza" in b:
        return "normativa urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "planos" in b or "planimetr" in b:
        return "planos planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    if "obra" in b:
        return "actuación urbanística"
    return "urbanismo"


class CartayaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 cartaya.es (normativa/agenda urbana) + sede espublico gestiona (tablón)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or DRUPAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.drupal_base = str(self.config.get("drupal_base") or DRUPAL_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
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
                    "Mozilla/5.0 (compatible; poc-bocm-cartaya/1.0)",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, url: str, base: str | None = None) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        root = (base or self.drupal_base).rstrip("/")
        return f"{root}{url if url.startswith('/') else '/' + url}"

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

    def _collect_drupal_pdfs(self) -> list[dict[str, Any]]:
        visited_pages: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        seen_pdfs: set[str] = set()
        rows: list[dict[str, Any]] = []

        while queue and len(visited_pages) < 35:
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in RE_NODE_HREF.finditer(html):
                node_url = self._abs_url(m.group(1))
                node_id = int(m.group(2))
                if node_url not in visited_pages and node_url not in queue and node_id >= 400:
                    queue.append(node_url)

            for m in RE_PDF_HREF.finditer(html):
                raw = m.group(0)
                href_m = re.search(r'href=["\']([^"\']+)["\']', raw, re.I)
                if not href_m:
                    continue
                pdf_url = self._abs_url(href_m.group(1))
                pdf_url = urllib.parse.unquote(pdf_url)
                if pdf_url in seen_pdfs or RE_SKIP_PDF.search(pdf_url):
                    continue
                title = _pdf_title(pdf_url)
                blob = f"{title} {pdf_url}"
                if not RE_PROYECTO.search(blob) and "agendaurbana" not in pdf_url.lower():
                    continue
                seen_pdfs.add(pdf_url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_urbanismo_news(self) -> list[dict[str, Any]]:
        url = f"{self.drupal_base}/es/areas-municipales/noticias/urbanismo"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_NEWS_HREF.finditer(html):
            news_url = self._abs_url(m.group(1))
            if "categorias" in news_url or news_url in seen:
                continue
            seen.add(news_url)
            slug = news_url.rstrip("/").rsplit("/", 1)[-1]
            titulo = slug.replace("-", " ").strip()
            if not RE_PROYECTO.search(titulo) and not re.search(r"(?i)obra", titulo):
                continue
            fecha = None
            try:
                detail = self._fetch(news_url)
                title_m = re.search(r"<title>([^<|]+)", detail, re.I)
                if title_m:
                    titulo = _strip_html(title_m.group(1)).replace("| Ayuntamiento de Cartaya", "").strip()
                date_m = RE_NEWS_DATE.search(detail)
                if date_m:
                    fecha = date_m.group(1)
            except urllib.error.URLError:
                pass
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": news_url,
                    "fecha": fecha or _fecha_from_blob(titulo),
                    "blob": titulo,
                    "origen": "drupal_news",
                }
            )
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Agenda Urbana de Cartaya (documento PDF)",
                "url": AGENDA_URBANA_PDF,
                "fecha": "2018-01-01",
                "blob": "Agenda Urbana Cartaya planeamiento estratégico",
                "tipo": "agenda urbana",
                "origen": "drupal_pdf",
            },
            {
                "titulo": "PGOU Cartaya — consulta SITUA (Junta de Andalucía)",
                "url": SITUA_SEARCH,
                "fecha": None,
                "blob": "Planeamiento general ordenación urbana Cartaya SITUA",
                "tipo": "PGOU",
                "origen": "situa",
            },
            {
                "titulo": "Portal transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                "url": f"{self.sede_base}/transparency/",
                "fecha": None,
                "blob": "Transparencia urbanismo obras públicas medio ambiente Cartaya",
                "tipo": "urbanismo",
                "origen": "sede_transparency",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
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
                "nota": "Requiere identificación Cl@ve/certificado",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.drupal_base}/es/tramites/descarga-de-documentos"),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Descarga de documentos / instancias urbanismo",
                "url": f"{self.drupal_base}/es/tramites/descarga-de-documentos",
                "source": "ayuntamiento",
                "nota": "Formularios e instancias de trámites (sin listado de concesiones)",
                "origen": "drupal_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "normativa")):
            return True
        if "urbanismo" in cat:
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
        elif "cesi" in blob.lower():
            tipo = "cesión administrativa licencia"
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc and "normativa" not in proc:
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

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "drupal",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "drupal_tramite")),
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

        for item in self._collect_static_proyectos():
            add(self._row_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_drupal_pdfs():
            add(self._row_to_proyecto(item))
        for item in self._collect_urbanismo_news():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal_pdf": sum(1 for r in rows if r.get("origen") == "drupal_pdf"),
            "drupal_news": sum(1 for r in rows if r.get("origen") == "drupal_news"),
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
