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

WEB_BASE = "https://www.lebrija.es"
SEDE_BASE = "https://sede.lebrija.es"
TRANSP_BASE = "https://transparencia.lebrija.es"
MUNICIPIO = "Lebrija"
ID_PREFIX = "lebrija"
INE_CODE = "41064"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
DEFAULT_TRANSP_INDICATORS: list[str] = [
    f"{TRANSP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00008/",
    f"{TRANSP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00008/",
    f"{TRANSP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00008/",
    f"{TRANSP_BASE}/es/transparencia/indicadores-de-transparencia/indicador/Usos-y-destinos-del-suelo-00008/",
]
SITUA_SEARCH_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41064"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|catalogo|catálogo|consulta p[uú]blica|avance|"
    r"expropiaci[oó]n|calificaci[oó]n ambiental|peri|uzo|terminaci[oó]n urbanizaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"activat joven|auxiliar administrativo|moad)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|convenio|expropiaci[oó]n)",
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)


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
    if "convenio" in blob and "urban" in blob:
        return "convenio urbanístico"
    if "expropiaci" in blob:
        return "expropiación"
    if "calificaci" in blob and "ambiental" in blob:
        return "calificación ambiental"
    if "plan parcial" in blob or "peri" in blob or " pp " in blob:
        return "plan parcial"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "consulta" in blob and "pública" in blob or "consulta publica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "catalogo" in blob or "catálogo" in blob:
        return "planeamiento"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    if "plano" in blob and "suelo" in blob:
        return "ordenación suelo"
    return "urbanismo"


class LebrijaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS web + GSede sede + portal transparencia Comentta (Sevilla/Andalucía)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRANSP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transp_indicators = [
            str(u) for u in (self.config.get("transparencia_indicators") or DEFAULT_TRANSP_INDICATORS)
        ]
        self.situa_search_url = str(self.config.get("situa_search_url") or SITUA_SEARCH_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "Mozilla/5.0 poc-bocm-lebrija/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

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

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page_url in self.transp_indicators:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            indicator = page_url.rstrip("/").rsplit("/", 1)[-1][:60]
            for href, inner in RE_LINK.findall(html):
                if ".pdf" not in href.lower():
                    continue
                url = _abs_url(href, self.transp_base)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = _strip_html(inner) or Path(urllib.parse.unquote(url.split("?")[0])).name
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(title, url),
                        "indicator": indicator,
                        "blob": f"{title} {indicator}",
                        "origen": "transparencia_pdf",
                    }
                )
        return rows

    def _collect_situa_seed(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.situa_search_url)
        except urllib.error.URLError:
            return []
        if "lebrija" not in html.lower() and "41064" not in html:
            return []
        return [
            {
                "titulo": "Consulta SITUA — planeamiento urbanístico Lebrija (PGOU 28/01/2016)",
                "url": self.situa_search_url,
                "fecha": "2016-01-28",
                "blob": "PGOU Lebrija planeamiento SITUA Junta Andalucía",
                "origen": "situa",
            }
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS"):
            return True
        return bool(RE_TABLON_URBAN.search(blob) or RE_LICENCIA.search(blob))

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
        if not RE_TABLON_URBAN.search(blob) and asunto not in (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
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

    def _pdf_to_proyecto(self, doc: dict[str, Any], origen: str) -> dict[str, Any]:
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
            "origen": origen,
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico INPRO",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios — sede GSede Lebrija (INE 41064)",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — área Urbanismo (ticket GSede)",
                "url": f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transp_indicators[0]),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — indicadores PGOU y planeamiento",
                "url": self.transp_indicators[0],
                "source": "ayuntamiento",
                "origen": "transparencia",
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia")
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
        for doc in self._collect_transparencia_pdfs():
            add(self._pdf_to_proyecto(doc, "transparencia_pdf"))
        for item in self._collect_situa_seed():
            add(self._pdf_to_proyecto(item, "situa"))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_pdf"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
