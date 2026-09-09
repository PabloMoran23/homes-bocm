from __future__ import annotations

import hashlib
import json
import re
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

WEB_BASE = "https://www.bollullospardelcondado.es"
SEDE_BASE = "https://sede.bollullospardelcondado.es"
URBANISMO_URL = f"{WEB_BASE}/servicios/urbanismo"
ORDENANZAS_URL = f"{WEB_BASE}/ayuntamiento/ordenanzas/ordenanzas-urbanisticas-y-uso-del-suelo"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Bollullos Par del Condado"
ID_PREFIX = "bollullos-par-del-condado"
INE_CODE = "21019"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    ORDENANZAS_URL,
    f"{WEB_BASE}/ayuntamiento/ordenanzas",
    f"{WEB_BASE}/ayuntamiento/convenios",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia de (?:pesca|apertura|taxi))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|unidad de ejecuci[oó]n|ue-|suro|surs|avance|"
    r"nnss|normas subsidiarias|eae|die\b|gesti[oó]n)",
)
RE_NOTICIA_URBAN = re.compile(
    r"(?i)(pgou|planeam|urbanismo|plan-parcial|plan-parcial|reparcel|"
    r"informaci[oó]n.*pgou|aprobado.*pgou|avance.*pgou|"
    r"licencia.*obra|licencia de obra|convenio urban|sector suro|sector surs|"
    r"unidad de ejecuci[oó]n|ordenanza urban)",
)
RE_NOTICIA_SKIP = re.compile(
    r"(?i)(licitaci[oó]n|servicio de|servicios de|autob[uú]s|feria|deporte|empleo|"
    r"piscina|carrera|fiestas|subvenci[oó]n|empadron|dni|biblioteca|"
    r"convenio de colaboraci|convenio anual|convenio de mutua|plan de igualdad|"
    r"plan de arreglo|plan-hebe|hora del planeta|plantar|cross-urbano|residuos)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_ANCHOR_PDF = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")
RE_FECHA_PUBLISHED = re.compile(r"Publicada:\s*(\d{1,2})-(\d{1,2})-(\d{4})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_NOTICIA_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_NOTICIA_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    m = RE_FECHA_PUBLISHED.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "convenio" in b and "gesti" in b:
        return "convenio urbanístico"
    if "reparcel" in b or "unidad de ejecuci" in b:
        return "reparcelación"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "eae" in b or "ambiental" in b:
        return "evaluación ambiental"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "avance" in b:
        return "avance planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class BollullosParDelCondadoAyuntamientoAdapter(AyuntamientoAdapter):
    """October CMS web (PDFs urbanismo/transparencia) + sede SWAL (sin tablón público scrapeable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-bollullos-par-del-condado/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{base or self.web_base}/", href)

    def _collect_page_pdfs(self, page_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_ANCHOR_PDF.finditer(html):
            href = self._abs_url(m.group(1), page_url)
            if href in seen:
                continue
            seen.add(href)
            anchor = _strip_html(m.group(2))
            if not anchor:
                anchor = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            blob = f"{anchor} {href} {page_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                if "/URBANISMO/" not in href.upper() and "pgou" not in href.lower():
                    continue
            rows.append(
                {
                    "titulo": anchor[:500],
                    "fecha": _fecha_from_blob(blob, href),
                    "url": page_url,
                    "pdf_url": href,
                    "blob": blob,
                    "origen": "web_pdf",
                }
            )

        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_url(m.group(1), page_url)
            if href in seen:
                continue
            seen.add(href)
            name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            blob = f"{name} {href} {page_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                if "/URBANISMO/" not in href.upper() and "pgou" not in href.lower():
                    continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(blob, href),
                    "url": page_url,
                    "pdf_url": href,
                    "blob": blob,
                    "origen": "web_pdf",
                }
            )
        return rows

    def _sitemap_noticia_urls(self) -> list[str]:
        try:
            xml = self._fetch(f"{self.web_base}/sitemap.xml")
        except urllib.error.URLError:
            return []
        root = ET.fromstring(xml)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls: list[str] = []
        for loc in root.findall(".//sm:loc", ns) or root.findall(".//loc"):
            u = (loc.text or "").strip()
            if "/noticias/" not in u or u.endswith("/noticias"):
                continue
            slug_part = u.rsplit("/", 1)[-1].lower()
            if RE_NOTICIA_SKIP.search(slug_part):
                continue
            if RE_NOTICIA_URBAN.search(slug_part):
                urls.append(u)
        return urls

    def _collect_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._sitemap_noticia_urls():
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title_m = RE_NOTICIA_H1.search(html) or RE_NOTICIA_TITLE.search(html)
            titulo = _strip_html(title_m.group(1)) if title_m else url.rsplit("/", 1)[-1]
            blob = f"{titulo} {_strip_html(html)[:2000]}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(html, url),
                    "url": url,
                    "blob": blob,
                    "origen": "web_noticia",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanismo y licencias",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Sede SWAL (ASP.NET); tablón de anuncios requiere autenticación",
                "origen": "sede",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "servicio urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Servicio de Urbanismo — documentación y trámites",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Sin listado histórico de licencias concedidas; solo PDFs de planeamiento",
                "origen": "web_urbanismo",
            },
            {
                "id": _stable_id("lic", ORDENANZAS_URL),
                "fecha_concesion": None,
                "tipo": "ordenanzas urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanzas urbanísticas y uso del suelo",
                "url": ORDENANZAS_URL,
                "source": "ayuntamiento",
                "nota": "Normativa municipal; no concesiones publicadas",
                "origen": "web_ordenanzas",
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
            "url": item.get("url", self.urbanismo_url),
            "source": "ayuntamiento",
            "pdf_url": pdf,
            "origen": item.get("origen"),
        }

    def _noticia_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = item.get("blob") or titulo
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _noticia_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
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
            rec = self._noticia_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for page_url in self.seed_pages:
            for item in self._collect_page_pdfs(page_url):
                add(self._pdf_to_proyecto(item))
        for item in self._collect_noticias():
            add(self._noticia_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Bollullos Par del Condado — consulta SITUA (Junta de Andalucía)",
                "fecha": "2023-12-22",
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": f"Visor regional SITUADIFusión; INE {INE_CODE}; sin API WFS pública por expediente",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
            "noticias": sum(1 for r in rows if r.get("origen") == "web_noticia"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
