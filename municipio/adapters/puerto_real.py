from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://puertoreal.es"
PGOU_URL = f"{WP_BASE}/aprobacion-definitiva-pgou/"
URBANISMO_URL = f"{WP_BASE}/atencion-a-la-ciudadania/servicios-municipales/urbanismo/"
SEDE_BASE = "https://sede.eprinsa.es/puertoreal"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Puerto Real"
ID_PREFIX = "puerto-real"
TIPO_ORDENANZA_URBANISTICA = 50

DEFAULT_SEED_PAGES = [PGOU_URL, URBANISMO_URL]

RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://puertoreal\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|concesi[oó]n de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|sectorizaci|reordenaci|actuaci[oó]n|calificaci[oó]n|"
    r"unidad de ejecuci|ue[\-\s]?\d|villanueva|aldea real|astilleros)",
)
RE_NOTICIA_SKIP = re.compile(
    r"(?i)(arbolado urbano|mobiliario urbano|urban[\-\s]?race|plan director de arbolado|"
    r"mantenimiento urbano|masa arb[oó]rea|farmacias|hospital|carnaval|deporte)",
)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_YOAST_JSON = re.compile(
    r'<script type="application/ld\+json" class="yoast-schema-graph">(.*?)</script>',
    re.S,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_blob(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"/(\d{4})/(\d{2})/", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "reparcel" in b:
        return "reparcelación"
    if "sectorizaci" in b:
        return "sectorización"
    if "plan parcial" in b or re.search(r"\bue[\-\s]?\d", b):
        return "plan parcial / unidad de ejecución"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b or "ordenaci" in b:
        return "ordenanza / ámbito planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    if "urbanizaci" in b:
        return "urbanización"
    return "urbanismo"


class PuertoRealAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress 6tems (PGOU PDFs, ordenanzas REST) + sede eprinsa (tablón SPA)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_noticias = int(self.config.get("max_noticias", 45))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "poc-bocm-puerto-real/1.0 (+urbanismo)",
                ),
            },
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name)).replace("-", " ").replace(".pdf", "")
                ctx_start = max(0, m.start() - 400)
                ctx = _strip_html(html[ctx_start : m.start() + 120])
                titulo = name[:500]
                if ctx and len(ctx) > 12 and "<" not in ctx:
                    snippet = ctx[-120:].strip()
                    if snippet:
                        titulo = snippet[:500]
                blob = f"{titulo} {pdf} {ctx}"
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(blob),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": blob,
                        "origen": "web_pgou" if "pgou" in page_url else "web_seed",
                    }
                )
        return rows

    def _collect_ordenanzas_urbanisticas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = (
                f"{self.wp_base}/wp-json/wp/v2/ordenanzas"
                f"?tipo_ordenanza={TIPO_ORDENANZA_URBANISTICA}&per_page=100&page={page}"
                f"&_fields=id,date,link,title,slug"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            for item in data:
                titulo = _strip_html(item.get("title", {}).get("rendered", ""))
                link = item.get("link") or ""
                fecha = (item.get("date") or "")[:10] or None
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "url": link,
                        "blob": titulo,
                        "origen": "wp_ordenanza_urb",
                    }
                )
            if len(data) < 100:
                break
            page += 1
        return rows

    def _noticia_sitemap_urls(self) -> list[str]:
        urls: list[str] = []
        for sm in ("noticia-sitemap.xml", "noticia-sitemap2.xml"):
            try:
                xml_text = self._fetch(f"{self.wp_base}/{sm}")
            except urllib.error.URLError:
                continue
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", ns):
                if loc.text:
                    urls.append(loc.text.strip())
        return urls

    def _yoast_from_html(self, html: str) -> tuple[str | None, str | None]:
        m = RE_YOAST_JSON.search(html)
        if not m:
            return None, None
        try:
            graph = json.loads(m.group(1))
        except json.JSONDecodeError:
            return None, None
        for node in graph.get("@graph", []):
            if node.get("@type") == "WebPage":
                name = node.get("name") or ""
                name = re.sub(r"\s*-\s*Ayuntamiento de Puerto Real\s*$", "", name).strip()
                published = (node.get("datePublished") or "")[:10] or None
                return name[:500] if name else None, published
        return None, None

    def _collect_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in self._noticia_sitemap_urls():
            slug_part = urllib.parse.unquote(url).lower()
            blob = slug_part.replace("-", " ")
            if RE_NOTICIA_SKIP.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            if url in seen:
                continue
            seen.add(url)
            if len(rows) >= self.max_noticias:
                break
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            titulo, fecha = self._yoast_from_html(html)
            if not titulo:
                titulo = _strip_html(re.search(r"<title>([^<]+)</title>", html, re.I).group(1))  # type: ignore[union-attr]
                titulo = re.sub(r"\s*-\s*Ayuntamiento de Puerto Real.*", "", titulo).strip()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha or _fecha_from_blob(url),
                    "url": url,
                    "blob": f"{titulo} {blob}",
                    "origen": "wp_noticia",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — licencias y urbanismo",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sede eprinsa (Diputación Córdoba); listado vía SPA Ember sin API pública",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público estructurado)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "servicio urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Servicio municipal de Urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Información y trámites presenciales; sin modelos PDF indexados en HTML estático",
                "origen": "web_urbanismo",
            },
        ]

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item["url"]
        blob = item.get("blob") or item.get("titulo", "")
        return {
            "id": _stable_id("proy", pdf),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", self.pgou_url),
            "source": "ayuntamiento",
            "pdf_url": item.get("pdf_url"),
            "origen": item.get("origen"),
        }

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = item.get("blob") or titulo
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _item_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "noticia urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
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
        for item in self._collect_noticias():
            rec = self._item_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_ordenanzas_urbanisticas():
            add(self._item_to_proyecto(item))
        for item in self._collect_noticias():
            add(self._item_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Puerto Real — consulta SITUA (Junta de Andalucía)",
                "fecha": "2025-01-01",
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; sin geometría por expediente municipal",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "wp_ordenanza_urb"),
            "noticias": sum(1 for r in rows if r.get("origen") == "wp_noticia"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
