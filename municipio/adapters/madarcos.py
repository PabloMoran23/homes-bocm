from __future__ import annotations

import hashlib
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

WEB_BASE = "https://madarcos.madrid"
SEDE_EADMIN = "https://sedemadarcos.eadministracion.es"
TABLON_URL = f"{SEDE_EADMIN}/PortalCiudadano/Tablon/wfrTablon.aspx"
TRANSPARENCIA_URL = "https://transparenciamadarcos.eadministracion.es/portal"
PGOU_URL = f"{WEB_BASE}/tu-ayuntamiento/normativa-municipal/plan-general-de-urbanismo"
ORDENANZAS_URL = f"{WEB_BASE}/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales"
TABLON_MUNI_URL = f"{WEB_BASE}/ciudadanos/tablon-municipal"
LICENCIAS_URL = f"{WEB_BASE}/ciudadanos/tramites-personales/instancias-licencias-y-solicitudes"
URBANISMO_URL = f"{WEB_BASE}/ciudadanos/tramites-personales/169-urbanismo"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
MUNICIPIO = "Madarcos"
ID_PREFIX = "madarcos"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|instancia general|tasa.*obra|maquinaria de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|bocm|ordenanza.*(?:urban|edificio|iee)|"
    r"bando.*(?:vivienda|parcela|pol[ií]gono|nave|arrendamiento)|minipol[ií]gono|"
    r"sit(?:cm)?|sistema de informaci[oó]n territorial|evaluaci[oó]n de edificios|"
    r"\biee\b|servicios urban|tasa.*maquinaria)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empadronamiento|bonificaci[oó]n ibi|familia numerosa|discapacidad.*veh[ií]culo|"
    r"ivtm|activaci[oó]n profesional|despoblamiento|fiestas|cobranza.*basura|"
    r"resoluci[oó]n.*incendio|fuegos artificiales|redes sociales|yoga|astro|"
    r"calendario de actividades|pleno.*convocatoria|leader 2026|itv m[oó]vil|"
    r"presupuesto general|encuentro de mayores|trabajador.?a social|canal de isabel|"
    r"estado de alarma|real decreto|abono social|tenientes de alcalde|transporte por carretera|"
    r"comercio y la hosteler[ií]a|tierra de oportunidades|emprendimiento|divulgaci[oó]n entomol|"
    r"recogida de residuos|designaci[oó]n tenientes|impuesto de bienes inmuebles|estacionamiento|"
    r"transito de ganado|arrendamiento de maquinaria(?! de obra))",
)
RE_ORDENANZA_PROYECTO = re.compile(
    r"(?i)(iee|evaluaci[oó]n de edificios|servicios urban|maquinaria de obra|"
    r"limpieza de solares|residuos.*construc|ocupaci[oó]n.*v[ií]a)",
)
RE_TABLON_PROYECTO = re.compile(
    r"(?i)(bando.*(?:vivienda|pol[ií]gono|nave|arrendamiento|parcela)|"
    r"minipol[ií]gono|concurso.*(?:vivienda|nave|arrendamiento))",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM = re.compile(
    r"BOCM\s*n[ºo°.]?\s*(\d+),\s*de\s+\w+\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
    re.I,
)
RE_BOCM_FILE = re.compile(r"BOCM[-_]?(\d{8})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_ARTICLE_LINK = re.compile(r'href="(/[^"]+/\d+-[^"]+)"')
RE_PDF = re.compile(r'(?:href|source)="([^"]+\.pdf[^"]*)"', re.I)
RE_IMG_PDF = re.compile(r"(/images/[^\"']+\.pdf)", re.I)
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": PGOU_URL,
        "titulo": "Plan General de Urbanismo de Madarcos — publicado en SITCM (aprobación 2015)",
        "fecha": "2015-01-01",
        "tipo": "PGOU",
        "origen": "pgou_seed",
    },
    {
        "url": SITCM_VISOR_URL,
        "titulo": "Visor cartográfico SITCM — planeamiento Comunidad de Madrid",
        "fecha": None,
        "tipo": "planeamiento",
        "origen": "sitcm_visor",
    },
]


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM.search(text or "")
    if m:
        try:
            day = int(m.group(2))
            month_name = m.group(3).lower()
            year = int(m.group(4))
            month = MONTHS.get(month_name) or MONTHS.get(month_name[:3])
            if month:
                return datetime(year, month, day).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    m = RE_BOCM_FILE.search(text or "")
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "iee" in n or "evaluaci" in n and "edificio" in n:
        return "ordenanza urbanística"
    if "bando" in n and ("vivienda" in n or "polígono" in n or "poligono" in n or "nave" in n):
        return "subasta / adjudicación"
    if "bocm" in n:
        return "publicación BOCM"
    if "maquinaria" in n and "obra" in n:
        return "ordenanza fiscal urbanística"
    if "sitcm" in n or "sistema de informaci" in n:
        return "planeamiento"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "instancia general" in n:
        return "instancia general"
    if "obra" in n:
        return "licencia de obra"
    return "trámite urbanístico"


class MadarcosAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla madarcos.madrid + sede eAdmin Maggioli (SPA, sin tablón scrapeable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transparencia_url = str(self.config.get("transparencia_url") or TRANSPARENCIA_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.tablon_muni_url = str(self.config.get("tablon_muni_url") or TABLON_MUNI_URL)
        self.licencias_url = str(self.config.get("licencias_url") or LICENCIAS_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, page_url: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(page_url or self.web_base)}/", href)

    def _article_title(self, html: str, fallback: str) -> str:
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            return _strip_html(m.group(1)).split(" - ")[0].strip()
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if h1:
            return _strip_html(h1.group(1))
        return fallback

    def _article_body(self, html: str) -> str:
        m = re.search(r'itemprop="articleBody"[^>]*>(.*?)</div>', html, re.S | re.I)
        return _strip_html(m.group(1)) if m else ""

    def _extract_pdfs(self, html: str, page_url: str) -> list[str]:
        seen: set[str] = set()
        pdfs: list[str] = []
        for pat in (RE_PDF, RE_IMG_PDF):
            for href in pat.findall(html):
                url = self._abs_url(href, page_url)
                if url not in seen:
                    seen.add(url)
                    pdfs.append(url)
        return pdfs

    def _parse_article_page(self, path: str, origen: str) -> dict[str, Any] | None:
        url = self._abs_url(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        title = self._article_title(html, path.rsplit("/", 1)[-1].replace("-", " "))
        body = self._article_body(html)
        blob = f"{title} {body}"
        if RE_EXCLUDE.search(blob):
            return None
        pdfs = self._extract_pdfs(html, url)
        return {
            "titulo": title[:500],
            "fecha": _parse_fecha_dmy(blob) or _parse_fecha_dmy(path),
            "url": url,
            "pdf_url": pdfs[0] if pdfs else None,
            "pdfs": pdfs,
            "origen": origen,
            "blob": blob,
        }

    def _collect_category_articles(self, list_url: str, origen: str, max_pages: int = 8) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        prefix = urllib.parse.urlparse(list_url).path.rstrip("/")
        effective_pages = 3 if origen == "joomla_tablon" else max_pages
        for page in range(effective_pages):
            url = list_url if page == 0 else f"{list_url}?start={page * 20}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            links = [
                m.group(1)
                for m in RE_ARTICLE_LINK.finditer(html)
                if m.group(1).startswith(prefix + "/") and "/170-noticias/" not in m.group(1)
            ]
            if not links:
                break
            new = 0
            for path in links:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                rec = self._parse_article_page(path, origen)
                if rec:
                    rows.append(rec)
                    new += 1
            if new == 0 and page > 0:
                break
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.static_proyectos:
            rows.append(
                {
                    "titulo": seed["titulo"][:500],
                    "fecha": seed.get("fecha"),
                    "url": seed["url"],
                    "origen": seed.get("origen", "static_seed"),
                    "tipo_hint": seed.get("tipo"),
                    "blob": seed["titulo"],
                }
            )
        try:
            html = self._fetch(self.pgou_url)
            body = self._article_body(html)
            if body:
                rows.append(
                    {
                        "titulo": "Normas subsidiarias / PGOU — información SITCM",
                        "fecha": "2015-01-01",
                        "url": self.pgou_url,
                        "origen": "pgou_page",
                        "blob": body,
                        "tipo_hint": "normas subsidiarias",
                    }
                )
        except urllib.error.URLError:
            pass
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sede_eadmin),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites urbanísticos",
                "url": self.sede_eadmin,
                "source": "ayuntamiento",
                "nota": "Presentación telemática (Maggioli SPA)",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "eAdmin requiere JS; petición directa devuelve sesión caducada",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.transparencia_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia municipal",
                "url": self.transparencia_url,
                "source": "ayuntamiento",
                "nota": "Transparencia eAdmin (Maggioli)",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", self.licencias_url),
                "fecha_concesion": None,
                "tipo": "instancias y solicitudes",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Instancias, licencias y solicitudes — impreso general",
                "url": self.licencias_url,
                "source": "ayuntamiento",
                "nota": "Instancia general para trámites sin formulario específico",
                "origen": "joomla_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — contacto técnico municipal",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Atención presencial martes a viernes 10:00–15:00",
                "origen": "joomla_urbanismo",
            },
        ]

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(row.get("titulo") or ""),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _proyecto_allowed(self, row: dict[str, Any]) -> bool:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return False
        origen = str(row.get("origen") or "")
        if origen == "joomla_ordenanza":
            return bool(RE_ORDENANZA_PROYECTO.search(blob))
        if origen == "joomla_tablon":
            return bool(RE_TABLON_PROYECTO.search(blob))
        return bool(RE_PROYECTO.search(blob))

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')} {row.get('pdf_url', '')}"
        if not self._proyecto_allowed(row):
            return None
        key = row.get("pdf_url") or row["url"]
        tipo = row.get("tipo_hint") or _proyecto_tipo(row.get("titulo") or blob)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _collect_source_rows(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for rec in self._collect_static_proyectos():
            key = rec["url"]
            by_key[key] = rec
        for rec in self._collect_category_articles(self.ordenanzas_url, "joomla_ordenanza"):
            key = rec.get("pdf_url") or rec["url"]
            by_key.setdefault(key, rec)
        for rec in self._collect_category_articles(self.tablon_muni_url, "joomla_tablon"):
            key = rec["url"]
            by_key.setdefault(key, rec)
        return list(by_key.values())

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
        for item in self._collect_source_rows():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("sede_", "transparencia", "joomla_"))),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_source_rows():
            rec = self._row_to_licencia(item)
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
        for item in self._collect_source_rows():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "joomla_ordenanza"),
            "tablon": sum(1 for r in rows if r.get("origen") == "joomla_tablon"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
