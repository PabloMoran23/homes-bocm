from __future__ import annotations

import hashlib
import http.cookiejar
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

WEB_BASE = "https://www.coriadelrio.es"
SEDE_BASE = "https://sede.coriadelrio.es"
TRANSPARENCIA_BASE = "https://transparencia.coriadelrio.es"
MUNICIPIO = "Coria del Río"
ID_PREFIX = "coria-del-rio"
INE_CODE = "41034"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
PGOM_URL = f"{WEB_BASE}/es/ciudadania/page-00001/"
PGOM_EXTERNAL = "https://nuevoplandecoriadelrio.es/"
NNSS_URL = f"{WEB_BASE}/es/ciudadania/normas-subsidiarias-municipales/"
NORMATIVA_URL = f"{WEB_BASE}/es/ayuntamiento/normativa"
FORMULARIOS_URL = f"{WEB_BASE}/es/ayuntamiento/formularios-disponibles/"
LICYTAL_URL = "https://sedeelectronicadipusevilla.es/LicytalSede/jsp/index.faces?cif=P4103400J"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
TRANSPARENCIA_NORMATIVA = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Se-publica-la-Normativa-municipal-tanto-del-Ayuntamiento-como-de-los-Entes-instrumentales-"
    "Relacion-de-normativa-en-curso-Ordenanzas-y-texto-en-version-inicial-memorias-e-informes-"
    "de-elaboracion-de-las-normativas.-00019/"
)

DEFAULT_PLANEAMIENTO_PAGES: list[str] = [
    PGOM_URL,
    NNSS_URL,
    NORMATIVA_URL,
    f"{WEB_BASE}/es/ciudadania/plan-de-biodiversidad-urbana/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|potaus|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|normas subsidiarias|catalogo|catálogo|"
    r"consulta p[uú]blica|avance|alteraci[oó]n.*t[eé]rminos|situa|vitua|biodiversidad urbana)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"activat joven|limpiador|auxiliar administrativo|pef construyendo|"
    r"cr[eé]dito extraordinario|moad|piscina climatizada|preinscripci[oó]n|"
    r"censo electoral|convocatoria pleno|bolsa 20\d{2}|itinerarios de inserci[oó]n)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|potaus|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|alteraci[oó]n.*t[eé]rminos|"
    r"convenio urban|v[ií]a pecuaria|ocupaci[oó]n)",
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "CONVOCATORIA",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
        "PUBLICACIÓN PARA CONOCIMIENTO GENERAL",
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
    if "pgom" in blob or "plan general" in blob or "planeamiento general" in blob:
        return "PGOM"
    if "normas subsidiarias" in blob or "nnss" in blob:
        return "normas subsidiarias"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "consulta" in blob and ("pública" in blob or "publica" in blob):
        return "información pública"
    if "ordenanza" in blob or "alteración" in blob and "términos" in blob:
        return "ordenanza urbanística"
    if "biodiversidad" in blob:
        return "plan urbanístico"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    if "situa" in blob:
        return "PGOM"
    return "urbanismo"


class CoriaDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS INPRO web + GSede sede propia + tablón INPRO Diputación Sevilla."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgom_url = str(self.config.get("pgom_url") or PGOM_URL)
        self.planeamiento_pages = [
            str(u) for u in (self.config.get("planeamiento_pages") or DEFAULT_PLANEAMIENTO_PAGES)
        ]
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.formularios_url = str(self.config.get("formularios_url") or FORMULARIOS_URL)
        self.licytal_url = str(self.config.get("licytal_url") or LICYTAL_URL)
        self.transparencia_normativa_url = str(
            self.config.get("transparencia_normativa_url") or TRANSPARENCIA_NORMATIVA
        )
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-coria-del-rio/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
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

    def _collect_document_links(self, page_url: str, base: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title or title.lower() in ("leer más", "leer mas", "pdf"):
                continue
            low_href = href.lower()
            if not any(x in low_href for x in (".pdf", ".zip", "/galleries/", "documentos-general")):
                continue
            url = _abs_url(href, base)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": title[:500], "url": url, "page": page_url})
        return rows

    def _collect_planeamiento_documents(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.planeamiento_pages:
            base = self.web_base if page_url.startswith(self.web_base) else page_url
            for doc in self._collect_document_links(page_url, base):
                if doc["url"] in seen_urls:
                    continue
                seen_urls.add(doc["url"])
                rows.append(doc)
        return rows

    def _collect_normativa_urbana(self) -> list[dict[str, Any]]:
        docs = self._collect_document_links(self.normativa_url, self.web_base)
        docs.extend(self._collect_document_links(self.transparencia_normativa_url, TRANSPARENCIA_BASE))
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for doc in docs:
            blob = f"{doc['titulo']} {doc['url']}"
            if not RE_PROYECTO.search(blob):
                continue
            if doc["url"] in seen:
                continue
            seen.add(doc["url"])
            doc = dict(doc)
            doc["origen"] = "normativa_urbana"
            out.append(doc)
        return out

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "PGOM Coria del Río — portal municipal",
                "url": self.pgom_url,
                "fecha": None,
                "origen": "pgom_web",
            },
            {
                "titulo": "PGOM Coria del Río — web informativa del plan",
                "url": PGOM_EXTERNAL,
                "fecha": None,
                "origen": "pgom_external",
            },
            {
                "titulo": "PGOM Coria del Río — consulta SITUA (Junta de Andalucía)",
                "url": SITUA_SEARCH,
                "fecha": None,
                "origen": "situa",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
            "TRÁMITE DE INFORMACIÓN PÚBLICA DE EXPEDIENTE ADMINISTRATIVO",
            "TRAMITE DE INFORMACION PUBLICA DE EXPEDIENTE ADMINISTRATIVO",
        ):
            return True
        if "informaci" in asunto.lower() and "p" in asunto.lower() and "blica" in asunto.lower():
            if RE_TABLON_URBAN.search(blob) or RE_PROYECTO.search(blob):
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
        urban_asuntos = (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
            "TRÁMITE DE INFORMACIÓN PÚBLICA DE EXPEDIENTE ADMINISTRATIVO",
            "TRAMITE DE INFORMACION PUBLICA DE EXPEDIENTE ADMINISTRATIVO",
        )
        if not RE_TABLON_URBAN.search(blob) and asunto not in urban_asuntos:
            if not (RE_PROYECTO.search(blob) and "informaci" in blob.lower()):
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

    def _doc_to_proyecto(self, doc: dict[str, Any], origen: str) -> dict[str, Any]:
        titulo = doc["titulo"]
        url = doc["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _fecha_from_blob(titulo, url),
            "tipo": _proyecto_tipo(titulo, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }

    def _static_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", doc["url"]),
            "municipio": MUNICIPIO,
            "titulo": doc["titulo"],
            "fecha": doc.get("fecha"),
            "tipo": _proyecto_tipo(doc["titulo"], doc["url"]),
            "url": doc["url"],
            "source": "ayuntamiento",
            "origen": doc.get("origen", "pgom_web"),
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
                "titulo": "Tablón electrónico INPRO — sede Coria del Río",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/sede/index.html"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites y servicios",
                "url": f"{self.sede_base}/opencms/sede/index.html",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.licytal_url),
                "fecha_concesion": None,
                "tipo": "portal licencias Diputación de Sevilla",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de licencias — LicytalSede Diputación (P4103400J)",
                "url": self.licytal_url,
                "source": "ayuntamiento",
                "origen": "dipusevilla",
            },
            {
                "id": _stable_id("lic", self.formularios_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia y declaración responsable",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios — licencias, DR y comunicaciones previas",
                "url": self.formularios_url,
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.transparencia_normativa_url),
                "fecha_concesion": None,
                "tipo": "transparencia normativa urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — ordenanzas y normativa en curso",
                "url": self.transparencia_normativa_url,
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
                if r.get("origen")
                in ("sede_tablon", "sede_tramite", "dipusevilla", "web_tramite", "transparencia")
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
        for doc in self._collect_planeamiento_documents():
            add(self._doc_to_proyecto(doc, "planeamiento_web"))
        for doc in self._collect_normativa_urbana():
            add(self._doc_to_proyecto(doc, doc.get("origen", "normativa_urbana")))
        for doc in self._collect_static_proyectos():
            add(self._static_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "planeamiento": sum(1 for r in rows if r.get("origen") == "planeamiento_web"),
            "normativa": sum(1 for r in rows if r.get("origen") == "normativa_urbana"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "pgom": sum(1 for r in rows if r.get("origen") in ("pgom_web", "pgom_external")),
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
