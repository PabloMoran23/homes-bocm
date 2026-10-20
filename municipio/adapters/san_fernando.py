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

WEB_BASE = "https://www.sanfernando.es"
SEDE_BASE = "https://sede.sanfernando.es"
TABLON_VIGENTE_URL = f"{SEDE_BASE}/TablonAnuncios/TablonEdictos.asp?tipo=1&hidOptNav=76"
TABLON_HISTORICO_URL = f"{SEDE_BASE}/TablonAnuncios/HistoricoTablonEdictos.asp?tipo=1&hidOptNav=76"
URBANISMO_TRAMITES_URL = f"{SEDE_BASE}/Visor.asp?hidOptNav=125"
VISOR_GIS_HUB = "https://visor-municipalidadsf.hub.arcgis.com/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "San Fernando"
ID_PREFIX = "san-fernando"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ayto/visor.asp?hidOptNav=1076",
    f"{WEB_BASE}/ayto/visor.asp?hidOptNav=1182",
    f"{WEB_BASE}/ayto/visor.asp?hidOptNav=1278",
    f"{WEB_BASE}/ayto/visor.asp?hidOptNav=2109",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|hosteler)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local|"
    r"calificaci[oó]n ambiental|ocupaci[oó]n provisional)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|ari\b|aip\b|sus[\-\s]?\d|ue[\-\s]?\d|expropiaci[oó]n|"
    r"urbanizaci[oó]n|gesti[oó]n asistem|peprich|pmvs|actuaci[oó]n|delimitaci[oó]n|"
    r"calificaci[oó]n ambiental|evaluaci[oó]n ambiental)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó]n|polic[ií]a local|proceso selectivo|"
    r"pleno ordinario|junta de gobierno|extracto acta|orden del d[ií]a|"
    r"listado provisional de admitidos|concurso oficial de elecci[oó]n de salineras|"
    r"impuesto veh[ií]culos|iae 20\d{2}|nichos|cajeros autom[aá]ticos)",
)
RE_TABLON_ENTRY = re.compile(
    r'class="tituloAnuncio"[^>]*>\s*(.*?)\s*</p>.*?'
    r'class="infoAnuncio"[^>]*>\s*([^<]+).*?'
    r'(?:class="icoDescargaPDF"[^>]*href="([^"]+)")?',
    re.S | re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?sanfernando\.es)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_TRAMITE_ROW = re.compile(
    r'<span class="destacado1">(.*?)</span>.*?'
    r"(?:infoAlert\(&#39;([^']+)|href=\"([^\"]+detalleAdmin[^\"]+)\"|"
    r"href=\"(https://tramites\.sanfernando\.es[^\"]+)\")",
    re.S | re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
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


def _fecha_from_info(info: str) -> str | None:
    dates = RE_FECHA_DMY.findall(info or "")
    if not dates:
        return None
    d, mo, y = dates[0]
    try:
        return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "convenio" in b and "urban" in b:
        return "convenio urbanístico"
    if "reparcel" in b:
        return "reparcelación"
    if "expropiaci" in b:
        return "expropiación"
    if "peprich" in b or "casco hist" in b:
        return "plan especial protección"
    if "pmvs" in b or "plan municipal de vivienda" in b:
        return "plan municipal vivienda y suelo"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and ("pgou" in b or "plan" in b):
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "proyecto de urbanizaci" in b:
        return "proyecto de urbanización"
    if "gesti" in b and "asistem" in b:
        return "gestión urbanística"
    if re.search(r"\bari\b|\baip\b", b):
        return "actuación urbanística"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class SanFernandoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede propia (tablón edictos ASP) + web corporativa visor PGOU/planeamiento."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_vigente_url = str(self.config.get("tablon_vigente_url") or TABLON_VIGENTE_URL)
        self.tablon_historico_url = str(
            self.config.get("tablon_historico_url") or TABLON_HISTORICO_URL
        )
        self.urbanismo_tramites_url = str(
            self.config.get("urbanismo_tramites_url") or URBANISMO_TRAMITES_URL
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.include_historico_tablon = bool(self.config.get("include_historico_tablon", True))
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
                    "poc-bocm-san-fernando/1.0 (+urbanismo)",
                ),
            },
        )
        with urllib.request.urlopen(req, timeout=120, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.web_base)}/", href)

    def _parse_tablon_html(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ENTRY.finditer(html):
            titulo = _strip_html(m.group(1))
            if not titulo or len(titulo) < 8:
                continue
            info = _strip_html(m.group(2))
            pdf = m.group(3)
            pdf_url = self._abs_url(pdf, self.web_base) if pdf else None
            key = pdf_url or titulo
            if key in seen:
                continue
            seen.add(key)
            blob = f"{titulo} {info}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_info(info),
                    "url": pdf_url or self.tablon_vigente_url,
                    "pdf_url": pdf_url,
                    "blob": blob[:2500],
                    "origen": origen,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.tablon_vigente_url)
            rows.extend(self._parse_tablon_html(html, "tablon_vigente"))
        except urllib.error.URLError:
            pass
        if self.include_historico_tablon:
            try:
                html = self._fetch(self.tablon_historico_url)
                rows.extend(self._parse_tablon_html(html, "tablon_historico"))
            except urllib.error.URLError:
                pass
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            ctx_page = _strip_html(html)[:800]
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1), page_url)
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(urllib.parse.urlparse(pdf).path).name))
                blob = f"{ctx_page} {name} {pdf}"
                if RE_TABLON_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not re.search(
                    r"(?i)pgou|planeam|peprich|pmvs|ordenanza", name
                ):
                    continue
                rows.append(
                    {
                        "titulo": (name.rsplit(".", 1)[0] or name)[:500],
                        "fecha": _fecha_from_blob(pdf + " " + blob),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": blob[:2000],
                        "origen": "web_planeamiento",
                    }
                )
        return rows

    def _collect_tramites_informativos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.urbanismo_tramites_url)
        except urllib.error.URLError:
            return rows
        for m in RE_TRAMITE_ROW.finditer(html):
            titulo = _strip_html(m.group(1))
            if not titulo or len(titulo) < 10:
                continue
            url = m.group(2) or m.group(3) or m.group(4) or self.urbanismo_tramites_url
            url = self._abs_url(url, self.sede_base)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "tipo_tramite": "declaración responsable"
                    if "declaraci" in titulo.lower()
                    else "licencia / trámite urbanismo",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_TABLON_SKIP.search(blob) and not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
            return False
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_TABLON_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row.get("pdf_url") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.tablon_vigente_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — urbanismo y licencias",
                "url": self.tablon_vigente_url,
                "source": "ayuntamiento",
                "nota": "Sede sede.sanfernando.es; anuncios con PDF en www.sanfernando.es/tramites/Ficheros/Tablon/",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.urbanismo_tramites_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites electrónicos de urbanismo (sede)",
                "url": self.urbanismo_tramites_url,
                "source": "ayuntamiento",
                "nota": "Declaraciones responsables y licencia obra menor; sin histórico de concesiones estructurado",
                "origen": "sede_tramite",
            },
        ]
        for item in self._collect_tramites_informativos():
            rows.append(
                {
                    "id": _stable_id("lic", item["url"] + item["titulo"]),
                    "fecha_concesion": None,
                    "tipo": item.get("tipo_tramite") or "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede; no concesión publicada",
                    "origen": item.get("origen"),
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_licencia(item))
        for item in self._collect_licencia_info_pages():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

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
        result["added"] = max(0, after - before)
        return result

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._doc_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", VISOR_GIS_HUB),
                "municipio": MUNICIPIO,
                "titulo": "Visor territorial municipal (ArcGIS Hub)",
                "fecha": None,
                "tipo": "visor urbanístico",
                "url": VISOR_GIS_HUB,
                "source": "ayuntamiento",
                "origen": "visor_gis",
            }
        )
        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU San Fernando — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "web": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
            "referencia": sum(1 for r in rows if r.get("origen") in ("situa", "visor_gis")),
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
        result["added"] = max(0, after - before)
        return result
