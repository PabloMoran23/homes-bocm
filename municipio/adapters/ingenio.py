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

WP_BASE = "https://ingenio.es"
SEDE_BASE = "https://ingenio.sedelectronica.es"
MUNICIPIO = "Ingenio"
ID_PREFIX = "ingenio"

BOARD_URL = f"{SEDE_BASE}/board"
URBANISMO_URL = f"{WP_BASE}/urbanismo/"
PGOU_URL = f"{WP_BASE}/plan-general-de-ordenacion-urbana/"
CATALOGO_URL = f"{WP_BASE}/catalogo_arquitectonico/"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    PGOU_URL,
    CATALOGO_URL,
    f"{WP_BASE}/ingenio-avanza-en-la-revision-de-su-plan-general-de-ordenacion/",
    f"{WP_BASE}/la-revision-del-pgou-de-ingenio-avanza-segun-el-cronograma-establecido/",
    f"{WP_BASE}/la-revision-del-plan-general-de-ingenio-vuelve-a-abrirse-a-la-participacion-de-la-ciudadania/",
    f"{WP_BASE}/el-ayuntamiento-celebrara-unas-jornadas-participativas-para-recibir-aportaciones-de-la-ciudadania-al-pgo/",
    f"{WP_BASE}/jornada-de-participacion-ciudadana-para-la-validacion-de-la-agenda-urbana-y-del-plan-de-actuacion-integrado-pai-de-ingenio/",
    f"{WP_BASE}/ingenio-perfila-su-agenda-urbana-2030-con-la-participacion-ciudadana/",
    f"{WP_BASE}/nuevas-actuaciones-urbanisticas-en-la-villa-de-ingenio-para-optimizar-la-conectividad-y-las-zonas-comerciales/",
    f"{WP_BASE}/se-suspende-cautelarmente-la-concesion-de-licencias-urbanisticas-en-el-litoral-por-la-revision-del-deslinde-de-costas/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia urban|segregaci[oó]n|parcelaci[oó]n|"
    r"primera ocupaci[oó]n|habitabilidad|v[ií]a p[uú]blica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boc|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n|agenda urbana|"
    r"urbanizaci[oó]n|instrumento|revisi[oó]n|avance|cat[aá]logo|"
    r"clasificaci[oó]n de suelo|ordenaci[oó]n|cesi[oó]n de bien)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenciones entidades deportivas|bases reguladoras|junta de gobierno|"
    r"sesi[oó]n plenaria|convocatoria de el pleno|notario|edicto del notario|"
    r"prueba de conocimiento|listado provisional)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(carta-de-colores|procedimientos\.pdf$|actuaciones\.pdf$)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://ingenio\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ingenio\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)
RE_WP_POST_LINK = re.compile(
    r'href="(https://ingenio\.es/(?!wp-content|category|author|feed)[^"]+/)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})/(\d{2})/")
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


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r"<h1[^>]*>([^<]+)",
        r'<meta property="og:title" content="([^"]+)"',
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _pdf_title(url: str) -> str:
    name = Path(url).stem.replace("_", " ").replace("-", " ").replace(".", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "revisi" in b and ("pgo" in b or "pgou" in b or "plan general" in b):
        return "revisión PGO"
    if "agenda urbana" in b or "pai" in b:
        return "agenda urbana / PAI"
    if "plan especial" in b:
        return "plan especial"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGO"
    if "memoria" in b:
        return "memoria planeamiento"
    if re.search(r"planos?|plano", b):
        return "planos planeamiento"
    if "normas" in b and "ordenaci" in b:
        return "normas urbanísticas"
    if "ordenaci[oó]n pormenorizada" in b or "clasificaci" in b:
        return "ordenación pormenorizada"
    if "cat[aá]logo" in b:
        return "catálogo urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "ordenanza" in b:
        return "ordenanza"
    return "urbanismo"


class IngenioAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (PGOU PDFs, noticias) + sede espublico gestiona (tablón /board)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ingenio/1.0")},
        )
        if "sedelectronica" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(WP_BASE, href))

    def _discover_sitemap_posts(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for i in range(1, 12):
            try:
                xml = self._fetch(f"{WP_BASE}/post-sitemap{i}.xml")
            except urllib.error.URLError:
                continue
            for m in RE_SITEMAP_LOC.finditer(xml):
                loc = m.group(1).strip()
                low = loc.lower()
                if any(
                    k in low
                    for k in (
                        "pgo",
                        "pgou",
                        "plan-general",
                        "planeam",
                        "urbanismo",
                        "informacion-publica",
                        "agenda-urbana",
                        "licencia",
                        "convenio-urban",
                        "revision-del-plan",
                        "modificacion-del-planeamiento",
                    )
                ) and "cross-urbano" not in low and "revisiones-ordinarias" not in low:
                    if loc not in seen:
                        seen.add(loc)
                        urls.append(loc)
        return urls

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
            categoria = cells.get("class_boardCategory", "") or cells.get("class_category", "")
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

    def _collect_pdfs_from_pages(self, pages: list[str]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                url = self._abs_url(m.group(1))
                if url in seen or RE_SKIP_PDF.search(url):
                    continue
                if not RE_PROYECTO.search(url):
                    continue
                seen.add(url)
                title = _pdf_title(url)
                rows.append(
                    {
                        "titulo": title,
                        "url": url,
                        "fecha": _fecha_from_blob(title, url),
                        "blob": f"{title} {url}",
                        "origen": "wordpress_pdf",
                    }
                )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        post_urls = list(dict.fromkeys(self.seed_pages + self._discover_sitemap_posts()))
        for url in post_urls:
            if url in seen:
                continue
            seen.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, Path(url).stem.replace("-", " "))
            blob = f"{title} {_strip_html(html)[:800]}"
            if not RE_PROYECTO.search(blob):
                continue
            if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title,
                    "url": url,
                    "fecha": _fecha_from_blob(blob, url),
                    "blob": blob,
                    "origen": "wordpress_post",
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(URBANISMO_URL)
        except urllib.error.URLError:
            html = ""
        for m in RE_PDF_HREF.finditer(html):
            url = self._abs_url(m.group(1))
            title = _pdf_title(url)
            if not RE_LICENCIA.search(f"{title} {url}") and "Solicitud" not in title:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _fecha_from_blob(title, url),
                    "tipo": "formulario trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "wordpress_pdf",
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
                "nota": "Edictos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y comunicaciones previas",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias urbanísticas vía sede (sin listado histórico público de concesiones)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "trámites y formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — formularios y ordenanzas",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Formularios PDF de licencias, segregación y certificados urbanísticos",
                "origen": "wordpress_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "vía pública", "via publica")):
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
        elif re.search(r"(?i)obra|v[ií]a p[uú]blica", blob):
            tipo = "licencia de obra / vía pública"
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

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = item.get("blob") or item.get("titulo") or ""
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen", "wordpress"),
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
        for rec in self._collect_licencia_info_pages() + self._collect_licencia_tramites():
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "wordpress_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages() + self._collect_licencia_tramites():
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
        pdf_pages = [PGOU_URL, URBANISMO_URL, CATALOGO_URL]
        for item in self._collect_pdfs_from_pages(pdf_pages):
            add(self._item_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._item_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wordpress_pdf": sum(1 for r in rows if r.get("origen") == "wordpress_pdf"),
            "wordpress_post": sum(1 for r in rows if r.get("origen") == "wordpress_post"),
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
