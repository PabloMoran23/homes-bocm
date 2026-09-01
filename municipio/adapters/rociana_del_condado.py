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

SEDE_BASE = "https://rocianadelcondado.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://www.rocianadelcondado.es"
SITEMAP_URL = f"{WEB_BASE}/sitemap.xml"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Rociana del Condado"
ID_PREFIX = "rociana"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/servicios/urbanismo/",
    f"{WEB_BASE}/es/planeamiento-urbanistico/",
    f"{WEB_BASE}/es/planeamiento-urbanistico/planeamiento-municipal/",
    f"{WEB_BASE}/es/ayuntamiento/ordenanzas/",
    (
        f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/"
        "Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00039/"
    ),
    (
        f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/"
        "Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00039/"
    ),
    (
        f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/"
        "Se-publica-informacion-precisa-de-la-normativa-vigente-en-materia-de-gestion-urbanistica-del-Ayuntamiento.-00039/"
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|zonific|clasificaci[oó]n|"
    r"normativa urban|red viaria|red de abastecimiento|saneamiento|protecci[oó]n|"
    r"calidad ambiental|fotovolta|sotovoltaica|establecimiento de detalle|detalle urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padr[oó]n municipal|modificaci[oó]n.*presupuest|bolsa de empleo|"
    r"activa-t joven|punto vuela|formador|protecci[oó]n civil|barrendero)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://rocianadelcondado\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://www\.rocianadelcondado\.es)?/export/sites/rociana[^"\']+\.(?:pdf|PDF)[^"\']*)["\']',
    re.I,
)
RE_PAGE_HREF = re.compile(
    r'href=["\']((?:https://www\.rocianadelcondado\.es)?/es/(?:planeamiento|servicios/urbanismo|gobierno-abierto/portal-transparencia)[^"\']*)["\']',
    re.I,
)
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+\.pdf)</loc>", re.I)
RE_SKIP_PDF = re.compile(
    r"(?i)(proteccion-de-datos|protecci[oó]n de datos|presupuesto|empleo|convocatoria|"
    r"fiestas|feria|deporte|turismo|coronavirus|bando|apertura-sac|hebe.*sector|"
    r"cementerio|guarder|basuras|polideportivo|feria\.pdf|animales.peligrosos)",
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


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "NNSS"
    if "modificaci" in b and ("pgou" in b or "puntual" in b or "plan parcial" in b):
        return "modificación planeamiento"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "estudio de detalle" in b or "e. de detalle" in b or "establecimiento de detalle" in b:
        return "estudio de detalle"
    if "evaluaci" in b and "ambiental" in b or "calidad ambiental" in b:
        return "evaluación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "memoria" in b:
        return "memoria planeamiento"
    if "zonific" in b or "usos" in b:
        return "zonificación urbanística"
    if "clasificaci" in b and "suelo" in b:
        return "clasificación del suelo"
    if "protecci" in b:
        return "protección urbanística"
    if "ordenanza" in b or "normativa" in b:
        return "normativa urbanística"
    if "planeamiento general" in b or "pgou" in b:
        return "PGOU"
    if "licencia" in b:
        return "licencia publicada"
    if "situa" in b:
        return "planeamiento"
    return "urbanismo"


class RocianaDelCondadoAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Diputación Huelva (galerías/transparencia PDF) + sede espublico gestiona (tablón)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.sitemap_url = str(self.config.get("sitemap_url") or SITEMAP_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-rociana/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urllib.parse.urljoin(f"{self.web_base}/", url)

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

    def _collect_sitemap_pdfs(self) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(self.sitemap_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_SITEMAP_LOC.finditer(xml):
            pdf_url = m.group(1).strip()
            if "rociana" not in pdf_url.lower():
                continue
            if pdf_url in seen:
                continue
            title = _pdf_title(pdf_url)
            blob = f"{title} {pdf_url}"
            if RE_SKIP_PDF.search(blob):
                continue
            urban_gallery = "TRANSPARENCIA-EN-MATERIAS-DE-URBANISMO" in pdf_url
            planeamiento_gallery = "/planeamiento" in pdf_url.lower()
            if not urban_gallery and not planeamiento_gallery and not RE_PROYECTO.search(blob):
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "titulo": title[:500],
                    "url": pdf_url,
                    "fecha": _fecha_from_blob(blob),
                    "blob": blob,
                    "origen": "sitemap_pdf",
                }
            )
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        visited_pages: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        seen_pdfs: set[str] = set()
        rows: list[dict[str, Any]] = []

        while queue and len(visited_pages) < 20:
            page_url = self._abs_web(queue.pop(0))
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in RE_PAGE_HREF.finditer(html):
                next_url = self._abs_web(m.group(1))
                if next_url not in visited_pages and next_url not in queue:
                    queue.append(next_url)

            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_web(m.group(1))
                pdf_url = urllib.parse.unquote(pdf_url)
                if pdf_url in seen_pdfs:
                    continue
                title = _pdf_title(pdf_url)
                blob = f"{title} {pdf_url}"
                if RE_SKIP_PDF.search(blob) or not RE_PROYECTO.search(blob):
                    continue
                seen_pdfs.add(pdf_url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "page_url": page_url,
                        "origen": "web_pdf",
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
                "id": _stable_id("lic", f"{self.web_base}/es/servicios/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — trámites y normativa",
                "url": f"{self.web_base}/es/servicios/urbanismo/",
                "source": "ayuntamiento",
                "nota": "Planeamiento vigente: Normas Subsidiarias; licencias de obra",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(
            k in proc
            for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "ambiental", "genérico")
        ):
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "ambiental" not in proc:
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

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "web_pdf"),
        }

    def _situa_row(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.situa_url),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento general — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": self.situa_url,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "PGOU y modificaciones en visor regional SituaDIFusión (BOJA 2025 mod. puntual 1)",
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

        add(self._situa_row())
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_web_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_sitemap_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "sitemap_pdf": sum(1 for r in rows if r.get("origen") == "sitemap_pdf"),
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
