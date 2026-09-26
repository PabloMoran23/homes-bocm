from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://ayuntamientodebaza.es"
SEDE_BASE = "https://sede.ayuntamientodebaza.es"
TABLON_URL = f"{WP_BASE}/tramites/tablon-de-anuncios/"
URBANISMO_URL = f"{WP_BASE}/c-i-urbanismo-y-patrimonio/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Baza"
ID_PREFIX = "baza"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera utilizaci[oó]n|apertura de locales)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de impacto)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|avance)|parcela|suelo|sector|"
    r"cambio de uso|innovaci[oó]n|delimitaci[oó]n|sectorizaci[oó]n|sun[snp]|"
    r"normas urban|clasificaci[oó]n del suelo|ordenanza.*urban|patrimonio.*hist)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de trabajo|tribunal|activa-t joven|subvencion.*escolar|feria y fiestas|"
    r"cascamorras|concurso fotogr|decoraci[oó]n de casetas|bando municipal.*caballos|"
    r"participaci[oó]n ciudadana|movimiento asociativo|psicologo|policia local|"
    r"lector-contador|vigilante arbitrios|administrativo|peon)",
)
RE_WPFD_EXCLUDE = re.compile(
    r"(?i)(ordenanza-fiscal|tasa-|impuesto|basura|residuos|cobranza|peones-obras-publicas|"
    r"bolsa-de-trabajo|concurso-oposici|subvencion.*libros|feria|participacion-ciudadana)",
)
RE_TABLON_DL = re.compile(
    r'href="(https://ayuntamientodebaza\.es/download/1105/tablon-de-anuncios/\d+/[^"]+)"'
    r'[^>]*title="([^"]+)"',
    re.I,
)
RE_SITEMAP_LOC = re.compile(r"<loc>(https://ayuntamientodebaza\.es/[^<]+)</loc>", re.I)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://ayuntamientodebaza\.es)?/(?:download|wp-content)[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_PUBLISHED = re.compile(
    r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPDTE = re.compile(r"(?i)(?:expediente\s+|exp\.?\s*)?(\d{4}/\d{4})")


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
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b or "sus-i" in b:
        return "plan parcial"
    if "delimitaci" in b or "sectorizaci" in b or "suns" in b:
        return "delimitación / sectorización"
    if "innovaci" in b:
        return "innovación planeamiento"
    if "normas urban" in b or "clasificaci" in b and "suelo" in b:
        return "normativa urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "modificaci" in b:
        return "modificación PGOU"
    if "licencia" in b:
        return "licencia publicada"
    return "planeamiento"


class BazaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Soledad + WP File Download (tablón) + sede Berger Levrault + SITUADIFusión."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-baza/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

    def _collect_tablon_files(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for url, title in RE_TABLON_DL.findall(html):
            if url in seen:
                continue
            seen.add(url)
            blob = f"{title} {url}"
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": url,
                    "pdf_url": url,
                    "blob": blob,
                    "expte": RE_EXPDTE.search(title).group(1) if RE_EXPDTE.search(title) else None,
                    "origen": "tablon_wpfd",
                }
            )
        return rows

    def _collect_sitemap_urls(self, sitemap_path: str) -> list[str]:
        url = f"{self.wp_base}/{sitemap_path}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        return [m.group(1) for m in RE_SITEMAP_LOC.finditer(html)]

    def _wpfd_page_to_row(self, wpfd_url: str) -> dict[str, Any] | None:
        slug = wpfd_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        if RE_WPFD_EXCLUDE.search(slug):
            return None
        if not RE_PROYECTO.search(slug):
            return None
        titulo = slug[:500]
        rec: dict[str, Any] = {
            "titulo": titulo,
            "fecha": _fecha_from_blob(slug),
            "url": wpfd_url,
            "blob": slug,
            "expte": RE_EXPDTE.search(slug).group(1) if RE_EXPDTE.search(slug) else None,
            "origen": "wpfd_sitemap",
        }
        try:
            html = self._fetch(wpfd_url)
            pub_m = RE_PUBLISHED.search(html)
            if pub_m:
                rec["fecha"] = _iso_date_wp(pub_m.group(1)) or rec["fecha"]
            pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(html)]
            if pdfs:
                rec["pdf_url"] = pdfs[0]
        except urllib.error.URLError:
            pass
        return rec

    def _collect_wpfd_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for wpfd_url in self._collect_sitemap_urls("wp-sitemap-posts-wpfd_file-1.xml"):
            if "/wpfd_file/" not in wpfd_url:
                continue
            item = self._wpfd_page_to_row(wpfd_url)
            if item and item["url"] not in seen:
                seen.add(item["url"])
                rows.append(item)
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = self._abs_wp(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ")
            rows.append(
                {
                    "titulo": f"Modificación PGOU — {name}",
                    "fecha": _fecha_from_blob(pdf_url),
                    "url": self.urbanismo_url,
                    "pdf_url": pdf_url,
                    "blob": f"{name} PGOU Baza urbanismo",
                    "origen": "web_urbanismo",
                }
            )
        return rows

    def _collect_situa_row(self) -> dict[str, Any]:
        return {
            "titulo": "Plan General de Ordenación Urbana (PGOU) — consulta SITUADIFusión",
            "fecha": "2010-01-01",
            "url": SITUA_SEARCH,
            "blob": "PGOU Baza SITUADIFusión planeamiento Granada",
            "origen": "situa",
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "PDFs wpfd categoría 1105; edictos cuando se publiquen",
                "origen": "tablon",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Concejalía de Urbanismo y Patrimonio",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "trámites sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Berger Levrault",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Licencias y permisos vía sede; sin listado histórico público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/tramites/"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites municipales",
                "url": f"{self.wp_base}/tramites/",
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
        ]

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": "tablon",
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._row_to_proyecto(row)

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
        for item in self._collect_tablon_files():
            rec = self._tablon_to_licencia(item)
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
        for item in self._collect_tablon_files():
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

        for item in self._collect_tablon_files():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_wpfd_proyectos():
            add(self._row_to_proyecto(item))
        for item in self._collect_urbanismo_pdfs():
            add(self._row_to_proyecto(item))
        add(self._row_to_proyecto(self._collect_situa_row()))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_wpfd"),
            "wpfd": sum(1 for r in rows if r.get("origen") == "wpfd_sitemap"),
            "web": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
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
