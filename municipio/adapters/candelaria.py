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
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://www.candelaria.es"
SEDE_BASE = "https://sedeelectronica.candelaria.es"
MUNICIPIO = "Candelaria"
ID_PREFIX = "candelaria"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/areas/planificacion-y-gestion-urbanistica/",
    f"{WP_BASE}/areas/planificacion-y-gestion-urbanistica/page/2/",
    f"{WP_BASE}/areas/agenda-urbana-planificacion-y-gestion-ambiental/",
    f"{WP_BASE}/descarga-de-solicitudes-last/",
    f"{WP_BASE}/category/planificacion-gestion-urbanistica/",
    f"{WP_BASE}/candelaria-firma-un-convenio-con-el-colegio-de-arquitectos-para-agilizar-licencias-de-obra-pendientes/",
    f"{SEDE_BASE}/publico/edictos",
    f"{SEDE_BASE}/publico/tablon",
    f"{SEDE_BASE}/publico/procedimientos",
    f"{SEDE_BASE}/transparencia/indice/indicador/IT21/11",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado|zanja|gr[uú]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|pamu|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n.*(?:pgo|pgou|plan)|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|huertas)",
)
RE_NOISE = re.compile(
    r"(?i)(modificaci[oó]n de cr[eé]dito|modificaci[oó]n presupuestaria|lista cobratoria|"
    r"impuesto de actividades|iae 20\d\d|proceso selectivo|polic[ií]a local|padr[oó]n de habitantes|"
    r"baja definitiva|baja en el padr[oó]n|ayudas al estudio|cuenta general|"
    r"retirada veh[ií]culo|fibrocemento|mercadillo|piscina municipal)",
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?candelaria\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FORM_PDF = re.compile(
    r'href="([^"]*(?:SOL|SOLICITUD|LICENCIA|COMUNICACI|URBANIZ|VADO|ZANJA|GRUA|CAMBIO-USO)[^"]*\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)


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
            t = re.sub(r"\s*[-|–].*(?:Candelaria|Ayuntamiento).*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pamu" in b or "actuaci" in b and "medio urbano" in b:
        return "PAMU"
    if "plan parcial" in b or " sup " in b or "sup-" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b or "supletorio" in b:
        return "PGOU"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "ordenanza" in b:
        return "ordenanza"
    return "urbanismo"


class CandelariaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (urbanismo, formularios) + sede Galileo GIYS (edictos RSS, trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.edictos_rss = str(
            self.config.get("edictos_rss") or f"{self.sede_base}/publico/sindicacion/edictos/RSS"
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-candelaria/1.0")},
        )
        ctx = self._ssl_ctx if "candelaria.es" in url and "sedeelectronica" not in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or WP_BASE, href))

    def _discover_wp_posts(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for i in range(1, 8):
            sitemap = f"{WP_BASE}/post-sitemap{i}.xml"
            try:
                xml = self._fetch(sitemap)
            except urllib.error.URLError:
                continue
            for m in RE_SITEMAP_LOC.finditer(xml):
                loc = m.group(1).strip()
                low = loc.lower()
                if any(
                    k in low
                    for k in (
                        "informacion-publica",
                        "plan-general",
                        "pgo",
                        "pgou",
                        "planeam",
                        "urbanismo",
                        "licencia",
                        "convenio",
                        "pamu",
                        "urbanistic",
                    )
                ) and "expediente-academico" not in low:
                    if loc not in seen:
                        seen.add(loc)
                        urls.append(loc)
        return urls

    def _collect_edictos_rss(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml = self._fetch(self.edictos_rss)
        except urllib.error.URLError:
            return rows
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            date_el = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            url = (link_el.text or "").strip()
            desc = _strip_html(desc_el.text if desc_el is not None else "")
            blob = f"{title} {desc}"
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].replace("Z", "+0000"),
                        "%a, %d %b %Y %H:%M:%S %z",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = _fecha_from_blob(date_el.text)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": blob,
                    "origen": "sede_edictos_rss",
                }
            )
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        page_urls = list(dict.fromkeys([*self.seed_pages, *self._discover_wp_posts()]))
        for page_url in page_urls:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            blob = f"{title} {page_url}"
            fecha = _fecha_from_blob(f"{title} {page_url} {html[:2000]}")
            if not RE_NOISE.search(blob) and (
                RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)
            ):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": page_url,
                        "blob": blob,
                        "origen": "wordpress_page",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {name} {pdf}"
                if RE_NOISE.search(pdf_blob):
                    continue
                if not RE_PROYECTO.search(pdf_blob) and not RE_LICENCIA.search(pdf_blob):
                    continue
                rows.append(
                    {
                        "titulo": f"{title}: {name}"[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "wordpress_pdf",
                    }
                )
            for m in RE_WP_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if not re.search(r"(?i)wp-content/uploads.*\.pdf", href):
                    continue
                pdf = self._abs_url(href)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {anchor} {name} {pdf}"
                if RE_NOISE.search(pdf_blob):
                    continue
                if not RE_PROYECTO.search(pdf_blob) and not RE_LICENCIA.search(pdf_blob):
                    continue
                rows.append(
                    {
                        "titulo": (anchor if len(anchor) > 5 else f"{title}: {name}")[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "wordpress_pdf",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        info_pages = [
            (f"{WP_BASE}/descarga-de-solicitudes-last/", "Descarga de solicitudes — urbanismo y licencias"),
            (f"{self.sede_base}/publico/procedimientos", "Catálogo de procedimientos — sede electrónica"),
            (f"{self.sede_base}/publico/edictos", "Tablón de edictos y anuncios"),
            (f"{self.sede_base}/publico/tablon", "Tablón público — sede electrónica"),
        ]
        for url, titulo in info_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        try:
            html = self._fetch(f"{WP_BASE}/descarga-de-solicitudes-last/")
        except urllib.error.URLError:
            return rows
        seen_forms: set[str] = set()
        for m in RE_FORM_PDF.finditer(html):
            href = unescape(m.group(1))
            pdf = self._abs_url(href)
            if pdf in seen_forms:
                continue
            seen_forms.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            if not RE_LICENCIA.search(name):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", pdf),
                    "fecha_concesion": None,
                    "tipo": "formulario licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": f"Formulario — {name[:200]}",
                    "url": pdf,
                    "source": "ayuntamiento",
                    "origen": "modelo_formulario",
                }
            )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") in ("tramite_informativo", "modelo_formulario"):
            return row
        blob = row.get("blob") or ""
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada" if row.get("origen") == "sede_edictos_rss" else "licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_NOISE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_tramites()
        for row in self._collect_edictos_rss():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        for row in self._collect_wp_pages():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sede_galileo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_edictos_rss():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_wp_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sede_galileo"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
