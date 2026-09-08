from __future__ import annotations

import hashlib
import http.cookiejar
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

WP_BASE = "https://www.aznalcollar.es"
SEDE_BASE = "https://sedeaznalcollar.dipusevilla.es"
MUNICIPIO = "Aznalcóllar"
ID_PREFIX = "aznalcollar"
INE_CODE = "41013"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
DIPUSEVILLA_LICENCIAS = (
    "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4101300D"
)
SITEMAP_URL = f"{WP_BASE}/sitemap.xml"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/es/actualidad/noticias/Bando-Aprobacion-inicial-y-exposicion-publica-del-Plan-General-de-Ordenacion-Urbanistica-de-Aznalcollar./",
    f"{WP_BASE}/es/ayuntamiento/Tablon-Anuncios/Aprobacion-inicial-del-Plan-General-de-Ordenacion-Urbanistica-de-Aznalcollar.-00001",
    f"{WP_BASE}/es/ayuntamiento/Tablon-Anuncios/Aprobacion-de-Ordenanza-Municipal-Reguladora-Acuerdo-Plenario-y-Anuncio-BOP-Regulacion-de-la-contaminacion-acustica.",
    f"{WP_BASE}/es/ayuntamiento/Tablon-Anuncios/CONSULTA-PUBLICA-PREVIA-DEL-DOCUMENTO-DE-AVANCE-DEL-PLAN-ESPECIAL-PARQUE-MIRADOR-EN-EL-T.-M.-DE-AZNALCOLLAR-SEVILLA-PROMOVIDO-POR-EL-AYUNTAMIENTO-DE-AZNALCOLLAR",
    f"{WP_BASE}/es/actualidad/noticias/CONSULTA-PUBLICA-PREVIA-SOBRE-UN-PROYECTO-DE-ORDENANZA-REGULADORA-DE-LA-OCUPACION-DE-ESPACIOS-PUBLICOS-CON-MESAS-SILLAS-Descargar-documento/",
    f"{WP_BASE}/es/actualidad/noticias/ANUNCIO-PARA-LA-CONSULTA-PREVIA-A-LA-APROBACION-DE-ORDENANZAS-Y-REGLAMENTOS-MUNICIPALES-Leer-",
    f"{WP_BASE}/es/actualidad/noticias/Plan-de-Accion-Local-de-la-Agenda-Urbana-2022-2030",
    f"{WP_BASE}/es/ayuntamiento/normativa",
    f"{WP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00004/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|potaus|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|catalogo|catálogo|consulta p[uú]blica|avance|"
    r"agenda urbana|parque mirador|contaminaci[oó]n ac[uú]stica)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"activat joven|limpiador|auxiliar administrativo|pef construyendo|"
    r"cr[eé]dito extraordinario|moad|cobranza|oferta empleo|escuela de verano|"
    r"festivo local)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|potaus|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|parque mirador|"
    r"agenda urbana)",
)
RE_SITEMAP_URBAN = re.compile(
    r"(?i)(urban|planeam|pgou|pgom|licencia|ordenanza|consulta-publica|"
    r"exposicion-publica|plan-general|plan-especial|parque-mirador|tablon-anuncios)",
)
RE_BOP_ONLY = re.compile(r"(?i)\bbop\b|\bboja\b")
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
        "AREA DE EMPLEO",
        "AREA DE ALCALDIA",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_OG_TITLE = re.compile(r'<meta property="og:title" content="([^"]+)"', re.I)


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


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "plan especial" in blob or "parque mirador" in blob:
        return "plan especial"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "consulta" in blob and ("pública" in blob or "publica" in blob):
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "agenda urbana" in blob:
        return "planeamiento"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    return "urbanismo"


def _is_urban_blob(blob: str) -> bool:
    if RE_TABLON_NON_URBAN.search(blob):
        return False
    if RE_BOP_ONLY.search(blob) and not RE_PROYECTO.search(blob):
        return False
    return bool(RE_PROYECTO.search(blob) or RE_TABLON_URBAN.search(blob))


class AznalcollarAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS INPRO web + sede GSede Diputación Sevilla (tablón INPRO)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = list(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aznalcollar/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def _page_title(self, html: str, fallback_url: str) -> str:
        m = RE_OG_TITLE.search(html) or RE_TITLE.search(html)
        if m:
            title = _strip_html(m.group(1))
            if title and title.lower() not in {"ayuntamiento", "sede electrónica"}:
                return title[:500]
        slug = fallback_url.rstrip("/").split("/")[-1]
        return slug.replace("-", " ")[:500]

    def _parse_tablon_html(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in RE_TABLON_ROW.finditer(html):
            row_html = tr.group(1)
            hidden = [
                _strip_html(x)
                for x in re.findall(r'<td class="hidden">(.*?)</td>', row_html, re.S)
            ]
            if len(hidden) < 4:
                continue
            referencia, asunto, url_path = hidden[1], hidden[2], hidden[3]
            celdas = [
                _strip_html(x)
                for x in re.findall(
                    r'<td[^>]*class="celdaGrid"[^>]*>(.*?)</td>', row_html, re.S
                )
            ]
            extracto = celdas[0] if celdas else ""
            origen = celdas[1] if len(celdas) > 1 else ""
            fecha_raw = celdas[2] if len(celdas) > 2 else ""
            url = _abs_url(url_path, self.sede_base)
            titulo = extracto or asunto
            if referencia and referencia not in titulo:
                titulo = f"{titulo} (ref. {referencia})"
            rows.append(
                {
                    "referencia": referencia,
                    "asunto": asunto,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "origen_tablon": origen[:120],
                    "blob": f"{asunto} {extracto} {origen}",
                    "origen": "tablon_inpro",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, encoding="latin-1")
        except urllib.error.URLError:
            return []

        pages = {1}
        for m in re.finditer(r"d-16544-p=(\d+)", html):
            pages.add(int(m.group(1)))

        all_rows: list[dict[str, Any]] = []
        seen_refs: set[str] = set()
        for page in sorted(pages):
            if page == 1:
                page_html = html
            else:
                page_url = (
                    f"{self.sede_base}/tablon-1.0/do/anuncio/listado?"
                    f"d-16544-p={page}&ine={INE_CODE}&cmd=ANUN00&opcionMenuIzda=1"
                )
                try:
                    page_html = self._fetch(page_url, encoding="latin-1")
                except urllib.error.URLError:
                    continue
            for row in self._parse_tablon_html(page_html):
                ref = row.get("referencia") or row["url"]
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
                all_rows.append(row)
        return all_rows

    def _collect_sitemap_urban_urls(self) -> list[str]:
        try:
            xml_text = self._fetch(SITEMAP_URL)
        except urllib.error.URLError:
            return []
        urls: list[str] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:loc", ns) or root.findall(".//loc"):
            if loc.text and RE_SITEMAP_URBAN.search(loc.text):
                url = loc.text.replace("http://", "https://")
                if "/actualidad/noticias/" in url or "/Tablon-Anuncios/" in url:
                    urls.append(url)
        return urls

    def _collect_seed_pages(self) -> list[str]:
        seen: set[str] = set()
        pages: list[str] = []
        for url in [*self.seed_pages, *self._collect_sitemap_urban_urls()]:
            norm = url.split("?")[0].rstrip("/")
            if norm not in seen and "index.html" not in norm:
                seen.add(norm)
                pages.append(norm if norm.endswith("/") else norm)
        return pages

    def _collect_pdf_links(self, page_url: str, base: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        page_title = self._page_title(html, page_url)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title or title.lower() in ("leer más", "leer mas", "descargar"):
                title = page_title
            low_href = href.lower()
            if ".pdf" not in low_href and "documentos-" not in low_href:
                continue
            url = _abs_url(href, base)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": title[:500] or page_title,
                    "url": url,
                    "page": page_url,
                    "page_title": page_title,
                }
            )
        return rows

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        for page_url in self._collect_seed_pages():
            norm = page_url.rstrip("/")
            if norm in seen_pages:
                continue
            seen_pages.add(norm)
            blob = urllib.parse.unquote(norm).replace("-", " ")
            if not _is_urban_blob(blob):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = self._page_title(html, page_url)
            if _is_urban_blob(page_title):
                rows.append(
                    {
                        "titulo": page_title,
                        "url": page_url,
                        "fecha": _fecha_from_blob(page_title, page_url),
                        "origen": "web_pagina",
                    }
                )
            for doc in self._collect_pdf_links(page_url, self.wp_base):
                blob_doc = f"{doc['titulo']} {doc['url']} {doc.get('page_title', '')}"
                if _is_urban_blob(blob_doc):
                    rows.append(
                        {
                            "titulo": doc["titulo"],
                            "url": doc["url"],
                            "fecha": _fecha_from_blob(doc["titulo"], doc["url"]),
                            "origen": "web_pdf",
                            "page": page_url,
                        }
                    )
        return rows

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS", "URBANISMO"):
            return True
        return _is_urban_blob(blob)

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("referencia") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_inpro",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not _is_urban_blob(blob) and asunto not in (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
            "URBANISMO",
        ):
            return None
        key = row.get("referencia") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row["url"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_inpro",
        }

    def _web_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
        titulo = doc["titulo"]
        url = doc["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": doc.get("fecha") or _fecha_from_blob(titulo, url),
            "tipo": _proyecto_tipo(titulo, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": doc.get("origen", "web"),
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico INPRO — sede Diputación Sevilla",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
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
                "origen": "dipusevilla",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/opencms/sede/index.html"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — área Urbanismo (ticket GSede)",
                "url": f"{self.sede_base}/opencms/opencms/sede/index.html",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/es/ayuntamiento/Tablon-Anuncios/"),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios web",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — web municipal",
                "url": f"{self.wp_base}/es/ayuntamiento/Tablon-Anuncios/",
                "source": "ayuntamiento",
                "origen": "web_tablon",
            },
        ]

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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tablon", "dipusevilla")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for doc in self._collect_web_proyectos():
            add(self._web_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        added = stats["rows"] - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": stats["rows"], "added": max(0, added), "status": "ok", **stats}
