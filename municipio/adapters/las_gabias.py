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

WP_BASE = "https://www.lasgabias.es/portal-transparencia"
SEDE_BASE = "https://lasgabias.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
JUNTA_PLANES_URL = (
    "https://www.juntadeandalucia.es/organismos/fomentoartesycultura/"
    "areas/vivienda-obras-publicas/planes-urbanisticos/consulta.html"
)
URBANISMO_PAGE_ID = 1942
MUNICIPIO = "Las Gabias"
ID_PREFIX = "las-gabias"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia de apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|innovaci[oó]n|expropiaci[oó]n|calificaci[oó]n ambiental|"
    r"ordenanza|ioud|metropolitano|vial|vivienda protegida)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|junta de gobierno local|cuenta general|presupuesto|"
    r"listado provisional admitidos|arquitecto|pe[oó]n de servicios)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://lasgabias\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://lasgabias\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r"href=['\"]((?:https://www\.lasgabias\.es)?/portal-transparencia/[^'\"]+\.pdf[^'\"]*)['\"]",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-/](\d{2})[-/]")
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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _fecha_from_blob(Path(url).name)


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "innovaci" in b:
        return "innovación planeamiento"
    if "plan parcial" in b or "pp " in b:
        return "plan parcial"
    if "expropiaci" in b:
        return "expropiación"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "memoria" in b:
        return "memoria"
    if "plano" in b:
        return "plano"
    if "ordenanza" in b:
        return "ordenanza"
    if "metropolitano" in b:
        return "infraestructura"
    return "urbanismo"


def _pdf_tipo(name: str) -> str:
    return _proyecto_tipo(name)


class LasGabiasAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress portal transparencia + sede espublico gestiona (tablón, catálogo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.urbanismo_page_id = int(self.config.get("urbanismo_page_id") or URBANISMO_PAGE_ID)
        self.situa_search = str(self.config.get("situa_search_url") or SITUA_SEARCH)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-las-gabias/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

    def _collect_urbanismo_pages(self) -> list[dict[str, Any]]:
        queue = [self.urbanismo_page_id]
        seen_ids: set[int] = set()
        pages: list[dict[str, Any]] = []
        while queue:
            pid = queue.pop(0)
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            try:
                page = self._fetch_json(f"{self.wp_base}/wp-json/wp/v2/pages/{pid}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            pages.append(page)
            try:
                children = self._fetch_json(
                    f"{self.wp_base}/wp-json/wp/v2/pages?parent={pid}&per_page=100"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if isinstance(children, list):
                for child in children:
                    cid = child.get("id")
                    if isinstance(cid, int):
                        queue.append(cid)
        return pages

    def _page_to_proyectos(self, page: dict[str, Any]) -> list[dict[str, Any]]:
        title = _strip_html(str((page.get("title") or {}).get("rendered") or ""))
        link = str(page.get("link") or "").strip()
        fecha = _iso_date_wp(str(page.get("modified") or page.get("date") or ""))
        content = str((page.get("content") or {}).get("rendered") or "")
        rows: list[dict[str, Any]] = []

        if title and link and RE_PROYECTO.search(title):
            rows.append(
                {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": link,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo_page",
                }
            )

        seen_pdfs: set[str] = set()
        for href in RE_PDF_HREF.findall(content):
            pdf = self._abs_wp(href)
            if pdf in seen_pdfs:
                continue
            seen_pdfs.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_title = f"{title}: {name}" if title else name
            if not RE_PROYECTO.search(f"{pdf_title} {name}"):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": pdf_title[:500],
                    "fecha": _fecha_from_url(pdf) or fecha,
                    "tipo": _pdf_tipo(name),
                    "url": link or pdf,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo_pdf",
                }
            )
        return rows

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for page in self._collect_urbanismo_pages():
            for rec in self._page_to_proyectos(page):
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.situa_search),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Las Gabias — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.situa_search,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; sin API por expediente",
            },
            {
                "id": _stable_id("proy", JUNTA_PLANES_URL),
                "municipio": MUNICIPIO,
                "titulo": "Consulta de planes urbanísticos y territoriales de Andalucía",
                "fecha": None,
                "tipo": "planeamiento",
                "url": JUNTA_PLANES_URL,
                "source": "ayuntamiento",
                "origen": "junta_consulta",
            },
        ]

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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        urbanismo_root = (
            f"{self.wp_base}/transparencia-en-materia-de-urbanismo-obras-publicas-y-medioambiente/"
        )
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y edictos urbanísticos",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": self.dossier_url,
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
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", urbanismo_root),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — urbanismo y planeamiento",
                "url": urbanismo_root,
                "source": "ayuntamiento",
                "nota": "Documentación PGOU, innovaciones y calificaciones ambientales",
                "origen": "wp_transparencia",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "expropiaci", "obra")):
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
        if not RE_PROYECTO.search(blob):
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

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("titulo") or ""):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": row["titulo"][:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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

        for rec in self._collect_static_proyectos():
            add(rec)
        for rec in self._collect_wp_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_items": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "static": sum(1 for r in rows if r.get("origen") in ("situa", "junta_consulta")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
