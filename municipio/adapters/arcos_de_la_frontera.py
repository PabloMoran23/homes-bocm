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

WP_BASE = "https://arcosdelafrontera.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
PGOU_BASE = "https://pgouarcos.es"
PGOU_API = f"{PGOU_BASE}/index.php?rest_route=/wp/v2"
SEDE_BASE = "https://sedelectronicaarcos.blcloud.es"
SEDE_CATALOG = f"{SEDE_BASE}/sede/catalogoTramites.do?opcion=detalle&idApl=3&ent_id=1&idioma=1"
MUNICIPIO = "Arcos de la Frontera"
ID_PREFIX = "arcos-de-la-frontera"

DEFAULT_PGOU_PAGES = [77, 100, 169]
DEFAULT_WEDOCS_ROOTS = [8311, 6593]
DEFAULT_SEED_PAGES = [
    f"{WP_BASE}/docs/planeamiento-en-tramitacion/",
    f"{WP_BASE}/docs/urbanismo/",
    f"{PGOU_BASE}/?page_id=77",
    f"{PGOU_BASE}/?page_id=100",
    f"{WP_BASE}/iii-tramites-urbanisticos/",
    f"{WP_BASE}/declaraciones-responsables-y-comunicaciones-previas/",
    f"{WP_BASE}/delegaciones/delegacion-de-urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|cedula|informaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|ambiental estrat[eé]gico)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|avance|regularizaci[oó]n|pepch|nnuu|pau|adaptaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(privacidad|cookies|aviso legal|registro de actividades|empleo p[uú]blico|"
    r"bolsa de empleo|concurso|oposici[oó]n|proceso selectivo|bando.*cultura|fiestas)",
)
RE_PDF_HREF = re.compile(
    r'(?:href|data)=["\']([^"\']+\.pdf(?:\.PDF)?[^"\']*)["\']',
    re.I,
)
RE_SEDE_TRAMITE = re.compile(
    r'title="([^"]+)"[^>]*href="javascript:\s*abrirLogin\(\'([^"\']+)\'\)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgom" in b or "pou" in b:
        return "planeamiento"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "estudio ambiental" in b or "eae" in b:
        return "estudio ambiental estratégico"
    if "plan especial" in b or "pepch" in b:
        return "plan especial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan municipal de vivienda" in b or "pmvs" in b:
        return "plan municipal vivienda y suelo"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "avance" in b:
        return "planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class ArcosDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Avada + weDocs + pgouarcos.es + sede blcloud (sin tablón público espublico)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api") or WP_API).rstrip("/")
        self.pgou_base = str(self.config.get("pgou_base") or PGOU_BASE).rstrip("/")
        self.pgou_api = str(self.config.get("pgou_api") or PGOU_API).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sede_catalog_url = str(self.config.get("sede_catalog_url") or SEDE_CATALOG)
        self.pgou_page_ids = [int(x) for x in (self.config.get("pgou_page_ids") or DEFAULT_PGOU_PAGES)]
        self.wedocs_roots = [int(x) for x in (self.config.get("wedocs_roots") or DEFAULT_WEDOCS_ROOTS)]
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-arcos-de-la-frontera/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
        for enc in ("utf-8", "iso-8859-1", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.wp_base, href))

    def _extract_pdfs(self, html: str, page_url: str) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        seen: set[str] = set()
        for href in RE_PDF_HREF.findall(html or ""):
            if RE_EXCLUDE.search(href):
                continue
            doc_url = self._abs_url(href, page_url)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            name = unescape(urllib.parse.unquote(Path(urllib.parse.urlparse(doc_url).path).name))
            found.append((name, doc_url))
        return found

    def _walk_wedocs(self, parent_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            docs = self._fetch_json(f"{self.wp_api}/docs?parent={parent_id}&per_page=100")
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        if not isinstance(docs, list):
            return rows
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            title = (doc.get("title") or {}).get("rendered") or ""
            link = str(doc.get("link") or "")
            date = _iso_date_wp(str(doc.get("date") or ""))
            doc_id = int(doc.get("id") or 0)
            rows.append(
                {
                    "titulo": _strip_html(title),
                    "fecha": date,
                    "url": link,
                    "blob": f"{title} {link}",
                    "origen": "wedocs",
                }
            )
            if doc_id:
                rows.extend(self._walk_wedocs(doc_id))
            if link:
                try:
                    html = self._fetch(link)
                    for name, pdf_url in self._extract_pdfs(html, link):
                        blob = f"{title} {name} {pdf_url} {link}"
                        if RE_EXCLUDE.search(blob):
                            continue
                        rows.append(
                            {
                                "titulo": f"{_strip_html(title)} — {name}"[:500],
                                "fecha": date or _fecha_from_blob(f"{name} {pdf_url}"),
                                "url": link,
                                "doc_url": pdf_url,
                                "blob": blob,
                                "origen": "wedocs_pdf",
                            }
                        )
                except urllib.error.URLError:
                    pass
        return rows

    def _collect_pgou_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_id in self.pgou_page_ids:
            try:
                page = self._fetch_json(f"{self.pgou_api}/pages/{page_id}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(page, dict):
                continue
            title = (page.get("title") or {}).get("rendered") or f"PGOU página {page_id}"
            link = str(page.get("link") or f"{self.pgou_base}/?page_id={page_id}")
            date = _iso_date_wp(str(page.get("modified") or page.get("date") or ""))
            content = (page.get("content") or {}).get("rendered") or ""
            for name, pdf_url in self._extract_pdfs(content, link):
                blob = f"{title} {name} {pdf_url}"
                rows.append(
                    {
                        "titulo": f"{_strip_html(title)} — {name}"[:500],
                        "fecha": date or _fecha_from_blob(f"{name} {pdf_url}"),
                        "url": link,
                        "doc_url": pdf_url,
                        "blob": blob,
                        "origen": "pgouarcos",
                    }
                )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for term in ("planeamiento", "urbanismo", "pgou", "pgom", "modificacion"):
            try:
                data = self._fetch_json(
                    f"{self.wp_api}/posts?search={urllib.parse.quote(term)}&per_page=50"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for post in data:
                title = (post.get("title") or {}).get("rendered") or ""
                link = str(post.get("link") or "")
                blob = f"{title} {link}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": _strip_html(title)[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": link,
                        "blob": blob,
                        "origen": "wordpress_post",
                    }
                )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for name, pdf_url in self._extract_pdfs(html, page_url):
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                blob = f"{name} {pdf_url} {page_url}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf_url}"),
                        "url": page_url,
                        "doc_url": pdf_url,
                        "blob": blob,
                        "origen": "wordpress_seed",
                    }
                )
        return rows

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.sede_catalog_url)
        except urllib.error.URLError:
            return rows
        urban_block = False
        for line in html.splitlines():
            if re.search(r">URBANISMO<", line, re.I):
                urban_block = True
                continue
            if urban_block and re.search(r'font-bold-500.*">[A-ZÁÉÍÓÚÑ ]+<', line) and "URBANISMO" not in line.upper():
                break
            if not urban_block:
                continue
            for title, js_url in RE_SEDE_TRAMITE.findall(line):
                title = _strip_html(title)
                if not title or RE_EXCLUDE.search(title):
                    continue
                if not RE_LICENCIA.search(title) and "urbanismo" not in title.lower():
                    continue
                tramite_path = js_url.replace("&amp;", "&")
                url = f"{self.sede_base}{tramite_path}" if tramite_path.startswith("/") else self.sede_catalog_url
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": None,
                        "url": url,
                        "blob": f"{title} {url}",
                        "origen": "sede_tramite",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.wp_base}/iii-tramites-urbanisticos/", "guía trámites urbanísticos"),
            (f"{self.wp_base}/declaraciones-responsables-y-comunicaciones-previas/", "declaraciones responsables"),
            (f"{self.wp_base}/tramites/", "trámites municipales (formularios PDF)"),
            (self.sede_catalog_url, "catálogo sede electrónica — urbanismo"),
        ]
        rows: list[dict[str, Any]] = []
        for url, label in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": label,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": label,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo; sin listado histórico de concesiones",
                    "origen": "tramite_info",
                }
            )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and row.get("origen") != "sede_tramite":
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("doc_url") or row.get("url") or row.get("titulo", "")
        tipo = "trámite urbanístico"
        if "comunicaci" in blob.lower():
            tipo = "comunicación previa"
        elif "declaraci" in blob.lower():
            tipo = "declaración responsable"
        elif "licencia" in blob.lower():
            tipo = "licencia urbanística"
        elif "cedula" in blob.lower() or "informaci" in blob.lower():
            tipo = "cédula / información urbanística"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo", "")[:500],
            "url": row.get("url"),
            "pdf_url": row.get("doc_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "sede_tramite":
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("doc_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo", "")[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("doc_url"):
            rec["pdf_url"] = row["doc_url"]
        return rec

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

    def _collect_all_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for root_id in self.wedocs_roots:
            rows.extend(self._walk_wedocs(root_id))
        rows.extend(self._collect_pgou_docs())
        rows.extend(self._collect_wp_posts())
        rows.extend(self._collect_seed_pdfs())
        rows.extend(self._collect_sede_tramites())
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_all_sources():
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") == "tramite_info"),
            "sede": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_all_sources():
            rec = self._to_licencia(item)
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
        for item in self._collect_all_sources():
            rec = self._to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgouarcos": sum(1 for r in rows if r.get("origen") == "pgouarcos"),
            "wedocs": sum(1 for r in rows if str(r.get("origen", "")).startswith("wedocs")),
            "posts": sum(1 for r in rows if r.get("origen") == "wordpress_post"),
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
