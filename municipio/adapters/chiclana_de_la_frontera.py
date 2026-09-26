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

TRANSP_BASE = "https://transparencia.chiclana.es"
WEB_BASE = "https://www.chiclana.es"
VENTANILLA_TABLON = (
    "https://ventanillavirtual.chiclana.es/web/tablonEdictos.do"
    "?entidad=CHICLANA&idioma=1&opcion=0"
)
VENTANILLA_LICENCIAS = (
    "https://ventanillavirtual.chiclana.es/web/tablonEdictos.do"
    "?entidad=CHICLANA&idioma=1&opcion=0&procedencia=LICENCIAS"
)
VENTANILLA_PLANEAMIENTO = (
    "https://ventanillavirtual.chiclana.es/web/tablonEdictos.do"
    "?entidad=CHICLANA&idioma=1&opcion=0&procedencia=PLANEAMIENTO"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
SITUA_CHICLANA = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?"
    "bXVuaWNpcGlvc3NlbGVjY2lvbmFkb3M9MTEwMTUmbXVuaWNpcGlvc1NlbGVjPUNISUNMQU5BIERFIExBIEZST05URVJBJm"
    "NvZGlnb3NNdW5pY2lwaW9zPTExMDE1JmNvZEZpZ3VyYT0yMTgzOSZqX2lkNjpqX2lkMzU9al9pZDY6al9pZDM1JmNo"
    "ZWNrQm94U2VsPWFwcm9iYWRvJmNvZEZpZ3VyYUJ1cz0yMTgzOSZEYXRhVGFibGVzX1RhYmxlXzBfbGVuZ3RoPTEwJmpf"
    "aWQ2PWpfaWQ2JmphdmF4LmZhY2VzLlZpZXdTdGF0ZT1qX2lkNCZ0aXR1bG9OTlNTUFA9UGxhbmVhbWllbnRvIGdlbm"
    "VyYWwgYXBwcm9iYWRvZGUgQ0hJQ0xBTkEgREUgTEEgRlJPTlRFUkEmY29kaWdvc05vbWJyZXNNdW5pY2lwaW9zPVt7"
    "ImlkIjoiMTEwMTUiLCJub21icmUiOiJDSElDTEFOQSBERSBMQSBGUk9OVEVSQSJ9XQ=="
)
MUNICIPIO = "Chiclana de la Frontera"
ID_PREFIX = "chiclana-de-la-frontera"

DEFAULT_TRANSP_SEEDS: list[str] = [
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/",
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/indicadores-sobre-urbanismo-y-obras-publicas/",
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/convenios-urbanisticos/",
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/proyectos-pliegos-y-criterios-de-licitacion-de-las-obras-publicas-mas-importantes/",
]

DEFAULT_STATIC_PROYECTOS: list[tuple[str, str, str, str | None]] = [
    (
        f"{WEB_BASE}/delegaciones-y-servicios/urbanismo/planeamiento-general/",
        "Planeamiento general — Normas Subsidiarias y revisión PGOU",
        "PGOU",
        "2021-12-15",
    ),
    (
        f"{WEB_BASE}/delegaciones-y-servicios/urbanismo/consulta-publica-previa-del-nuevo-plan-general-de-chiclana-de-la-frontera/",
        "Consulta pública previa del nuevo PGOU de Chiclana de la Frontera",
        "consulta previa PGOU",
        "2024-01-01",
    ),
    (
        f"{WEB_BASE}/areas-municipales/urbanismo-obra-y-vivienda/urbanismo/convenios-urbanisticos",
        "Convenios urbanísticos — delegación de urbanismo",
        "convenio urbanístico",
        None,
    ),
    (
        f"{WEB_BASE}/areas-municipales/urbanismo-obra-y-vivienda/delegacion-de-urbanismo/instrumentos-de-ordenacion-urbanistica-detallada",
        "Instrumentos de Ordenación Urbanística Detallada (IOUD)",
        "planeamiento",
        None,
    ),
    (
        f"{WEB_BASE}/areas-municipales/urbanismo-obra-y-vivienda/delegacion-de-urbanismo/instrumentos-complementarios-de-la-ordenacion-urbanistica",
        "Instrumentos Complementarios de la Ordenación Urbanística (IOCU)",
        "planeamiento",
        None,
    ),
    (
        "https://www.juntadeandalucia.es/boja/2016/233/19",
        "BOJA — Aprobación definitiva parcial revisión PGOU Chiclana (2016)",
        "revisión PGOU",
        "2016-11-28",
    ),
    (
        "https://www.juntadeandalucia.es/boja/2016/249/40",
        "BOJA — Normativa urbanística revisión PGOU Chiclana (2016)",
        "revisión PGOU",
        "2016-12-22",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|consulta p[uú]blica|instrumento|ioud|iocu|"
    r"delimitaci[oó]n|licitaci[oó]n.*obra|indicador.*urban|situa|vitua)",
)
RE_VENTANILLA_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|cobranza iae|padrones|polic[ií]a local|censo electoral|"
    r"carnaval|zambomba|incendios forestales|residuos s[oó]lidos)",
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,400})</a>', re.I | re.S)
RE_SKIP = re.compile(
    r"(?i)(favicon|facebook|twitter|instagram|youtube|#|javascript:|"
    r"wp-json|feed/|xmlrpc|accesibilidad|cookies|privacy|contrataciondelestado)",
)
RE_DOC_EXT = re.compile(r"(?i)\.(pdf|zip|odt|docx?)(\?|$)")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PATH = re.compile(r"/(20\d{2})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_VENTANILLA_ROW = re.compile(
    r"<tr[^>]*>(.*?)</tr>",
    re.I | re.S,
)


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
    m = RE_FECHA_PATH.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "consulta" in b and "pgou" in b:
        return "consulta previa PGOU"
    if "revisi" in b and "pgou" in b:
        return "revisión PGOU"
    if "nnss" in b or "normas subsidiarias" in b:
        return "NNSS"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "convenio" in b:
        return "convenio urbanístico"
    if "ioud" in b or "detallada" in b:
        return "IOUD"
    if "iocu" in b or "complementario" in b:
        return "IOCU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "indicador" in b and "urban" in b:
        return "indicadores urbanismo"
    if "licencia" in b:
        return "licencia publicada"
    if "licitaci" in b and "obra" in b:
        return "obra pública"
    return "urbanismo"


class ChiclanaDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    """Transparencia WordPress + ventanilla virtual (Cloudflare) + SITUA + web municipal (Cloudflare)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRANSP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.transp_seeds = [str(u) for u in (self.config.get("transparencia_seeds") or DEFAULT_TRANSP_SEEDS)]
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        self.ventanilla_tablon = str(self.config.get("ventanilla_tablon") or VENTANILLA_TABLON)
        self.ventanilla_licencias = str(self.config.get("ventanilla_licencias") or VENTANILLA_LICENCIAS)
        self.ventanilla_planeamiento = str(
            self.config.get("ventanilla_planeamiento") or VENTANILLA_PLANEAMIENTO
        )
        self.situa_search = str(self.config.get("situa_search") or SITUA_SEARCH)
        self.situa_chiclana = str(self.config.get("situa_chiclana") or SITUA_CHICLANA)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-chiclana-de-la-frontera/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.transp_base)}/", href)

    def _collect_transp_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.transp_seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            if title_m:
                page_title = _strip_html(title_m.group(1))

            for href in RE_HREF.findall(html):
                if RE_SKIP.search(href):
                    continue
                doc_url = self._abs_url(href, page_url)
                if doc_url in seen:
                    continue
                if not RE_DOC_EXT.search(doc_url):
                    continue
                name = unescape(urllib.parse.unquote(Path(doc_url.split("?")[0]).name))
                blob = f"{name} {doc_url} {page_title} {page_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": name[:500] if len(name) > 5 else page_title[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": doc_url,
                        "blob": blob,
                        "origen": "transparencia",
                        "seed_page": page_url,
                    }
                )
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo, tipo_hint, fecha in self.static_proyectos:
            blob = f"{titulo} {url} {tipo_hint}"
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": fecha or _fecha_from_blob(blob),
                    "url": url,
                    "blob": blob,
                    "tipo_hint": tipo_hint,
                    "origen": "static",
                }
            )
        rows.append(
            {
                "titulo": "PGOU Chiclana — consulta SITUA (Junta de Andalucía)",
                "fecha": "2016-01-01",
                "url": self.situa_chiclana,
                "blob": f"SITUA planeamiento general Chiclana {self.situa_chiclana}",
                "tipo_hint": "PGOU",
                "origen": "situa",
            }
        )
        rows.append(
            {
                "titulo": "Consulta planeamiento urbanístico Andalucía — SITUA",
                "fecha": None,
                "url": self.situa_search,
                "blob": f"SITUA search {self.situa_search}",
                "tipo_hint": "planeamiento",
                "origen": "situa",
            }
        )
        return rows

    def _collect_ventanilla(self, url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        if "Just a moment" in html or "challenge-error" in html:
            return []
        if "tablonEdictos" not in html and "Tablón" not in html and "TABL" not in html.upper():
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_VENTANILLA_ROW.finditer(html):
            row_html = m.group(1)
            text = _strip_html(row_html)
            if len(text) < 20:
                continue
            if RE_VENTANILLA_NON_URBAN.search(text) and not RE_LICENCIA.search(text):
                continue
            if not RE_LICENCIA.search(text) and not RE_PROYECTO.search(text):
                continue
            link_m = RE_LINK.search(row_html)
            doc_url = url
            if link_m:
                doc_url = self._abs_url(link_m.group(1), url)
            rows.append(
                {
                    "titulo": text[:500],
                    "fecha": _fecha_from_blob(text),
                    "url": doc_url,
                    "blob": text,
                    "origen": origen,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.ventanilla_licencias),
                "fecha_concesion": None,
                "tipo": "tablón edictos licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — Licencias (ventanilla virtual)",
                "url": self.ventanilla_licencias,
                "source": "ayuntamiento",
                "nota": "Filtro Licencias en ventanillavirtual.chiclana.es (Cloudflare en CI)",
                "origen": "ventanilla_info",
            },
            {
                "id": _stable_id("lic", self.ventanilla_tablon),
                "fecha_concesion": None,
                "tipo": "tablón edictos general",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — ventanilla virtual",
                "url": self.ventanilla_tablon,
                "source": "ayuntamiento",
                "nota": "Publicaciones administrativas incl. Planeamiento y Gestión",
                "origen": "ventanilla_info",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/delegaciones-y-servicios/urbanismo/tablon-de-anuncios/"),
                "fecha_concesion": None,
                "tipo": "tablón anuncios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — delegación urbanismo",
                "url": f"{self.web_base}/delegaciones-y-servicios/urbanismo/tablon-de-anuncios/",
                "source": "ayuntamiento",
                "nota": "Web municipal (Cloudflare); edictos licencias y planeamiento",
                "origen": "web_info",
            },
            {
                "id": _stable_id(
                    "lic",
                    f"{self.web_base}/delegaciones-y-servicios/urbanismo/tramites-y-procedimientos-delegacion-municipal-de-urbanismo/",
                ),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y procedimientos — delegación municipal de urbanismo",
                "url": f"{self.web_base}/delegaciones-y-servicios/urbanismo/tramites-y-procedimientos-delegacion-municipal-de-urbanismo/",
                "source": "ayuntamiento",
                "nota": "Formularios licencias/comunicaciones previas (sin histórico tabular)",
                "origen": "web_info",
            },
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        tipo = row.get("tipo_hint") or _proyecto_tipo(blob)
        url = row.get("url") or self.transp_base
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "transparencia"),
        }

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        url = row.get("url") or self.ventanilla_tablon
        return {
            "id": _stable_id("lic", url + (row.get("titulo") or "")),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "ventanilla"),
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
        for item in self._collect_ventanilla(self.ventanilla_licencias, "ventanilla_licencias"):
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_ventanilla(self.ventanilla_tablon, "ventanilla"):
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "ventanilla": sum(1 for r in rows if r.get("origen") == "ventanilla"),
            "info": sum(1 for r in rows if r.get("origen") in ("ventanilla_info", "web_info")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_ventanilla(self.ventanilla_licencias, "ventanilla_licencias"):
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

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_static_proyectos():
            add(self._to_proyecto(item))
        for item in self._collect_transp_docs():
            add(self._to_proyecto(item))
        for item in self._collect_ventanilla(self.ventanilla_planeamiento, "ventanilla_planeamiento"):
            if RE_PROYECTO.search(item.get("blob") or ""):
                add(self._to_proyecto(item))
        for item in self._collect_ventanilla(self.ventanilla_tablon, "ventanilla"):
            if RE_PROYECTO.search(item.get("blob") or ""):
                add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "static": sum(1 for r in rows if r.get("origen") == "static"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "ventanilla": sum(1 for r in rows if str(r.get("origen", "")).startswith("ventanilla")),
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
