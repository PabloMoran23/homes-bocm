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

WEB_BASE = "https://www.elcoronil.es"
SEDE_BASE = "https://sede.elcoronil.es"
TABLON_BASE = "https://sedeelectronicadipusevilla.es"
TRANSPARENCIA_BASE = "https://transparencia.elcoronil.es"
MUNICIPIO = "El Coronil"
ID_PREFIX = "el-coronil"
INE_CODE = "41036"

TABLON_URL = f"{TABLON_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
TRANSPARENCIA_URBAN = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "50.-Instrumentos-de-ordenacion-urbanistica/"
)
ORDENANZAS_URL = f"{WEB_BASE}/es/ayuntamiento/ordenanzas/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
PBOM_PORTAL_URL = "https://nuevoplanelcoronil.es/"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|catalogo|catálogo|consulta p[uú]blica|avance|"
    r"tip|oryp|instrumento)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"bando.*censo|bando.*jurado|expropiaci[oó]n forzosa|agricultura|boe.*inscripci)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|modificaci[oó]n puntual|"
    r"centro de salud)",
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
        "BANDOS",
        "SECRETARIA",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual PGOU"
    if "plan parcial" in blob or "sector" in blob and "molinos" in blob:
        return "plan parcial"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "pbom" in blob or "plan básico" in blob or "plan basico" in blob:
        return "PBOM"
    if "consulta" in blob and "pública" in blob or "consulta publica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    if "plano" in blob:
        return "cartografía urbanística"
    return "urbanismo"


class ElCoronilAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS web + GSede sede + tablón INPRO Diputación Sevilla (INE 41036)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_base = str(self.config.get("tablon_base") or TABLON_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transparencia_urban_url = str(
            self.config.get("transparencia_urban_url") or TRANSPARENCIA_URBAN
        )
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-coronil/1.0")},
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
            url = _abs_url(url_path, self.tablon_base)
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
                    f"{self.tablon_base}/tablon-1.0/do/anuncio/listado?"
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
        try:
            html = self._fetch(self.transparencia_urban_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = unescape(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            url = _abs_url(href, TRANSPARENCIA_BASE)
            filename = url.split("/")[-1]
            title_match = re.search(
                rf'title="([^"]+)"[^>]*href="{re.escape(href)}"',
                html,
                re.I | re.S,
            )
            if not title_match:
                title_match = re.search(
                    rf'href="{re.escape(href)}"[^>]*title="([^"]+)"',
                    html,
                    re.I | re.S,
                )
            titulo = _strip_html(title_match.group(1)) if title_match else filename
            titulo = re.sub(r"\s*\|\s*pdf\s*$", "", titulo, flags=re.I).strip() or filename
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "transparencia_urbana",
                }
            )
        return rows

    def _collect_ordenanzas_urbana(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ordenanzas_url)
        except urllib.error.URLError:
            return []
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title_attr, inner in RE_LINK.findall(html):
            title = _strip_html(title_attr or inner)
            if not title:
                continue
            blob = f"{title} {href}"
            if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                continue
            if ".pdf" not in href.lower() and "documentos/" not in href.lower():
                continue
            url = _abs_url(href, self.web_base)
            if url in seen:
                continue
            seen.add(url)
            out.append({"titulo": title[:500], "url": url, "origen": "ordenanzas_web"})
        return out

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS and not RE_TABLON_URBAN.search(blob):
            return False
        if RE_TABLON_NON_URBAN.search(blob) and not RE_TABLON_URBAN.search(blob):
            return False
        if asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS", "EDICTOS"):
            return bool(RE_TABLON_URBAN.search(blob) or RE_PROYECTO.search(blob))
        return bool(RE_TABLON_URBAN.search(blob) or RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

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
        if not (
            RE_TABLON_URBAN.search(blob)
            or RE_PROYECTO.search(blob)
            or asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS", "EDICTOS")
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
            "fecha": _fecha_from_blob(titulo, url),
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
                "tipo": "tablón electrónico de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico INPRO — Diputación Sevilla",
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
                "titulo": "Sede electrónica — trámites y expedientes",
                "url": f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transparencia_urban_url),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — instrumentos de ordenación urbanística",
                "url": self.transparencia_urban_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
        ]

    def _collect_situa_metadata(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", SITUA_SEARCH),
            "municipio": MUNICIPIO,
            "titulo": "PGOU El Coronil — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "PGOU",
            "url": SITUA_SEARCH,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional SituaDIFusión; sin geometría por expediente.",
        }

    def _collect_pbom_metadata(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", PBOM_PORTAL_URL),
            "municipio": MUNICIPIO,
            "titulo": "PBOM El Coronil — portal participación ciudadana",
            "fecha": "2025-06-30",
            "tipo": "PBOM",
            "url": PBOM_PORTAL_URL,
            "source": "ayuntamiento",
            "origen": "pbom_portal",
            "nota": "Portal con captcha; documentación en transparencia indicador 50.",
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

        add(self._collect_situa_metadata())
        add(self._collect_pbom_metadata())
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for doc in self._collect_transparencia_pdfs():
            add(self._pdf_to_proyecto(doc, doc.get("origen", "transparencia_urbana")))
        for doc in self._collect_ordenanzas_urbana():
            add(self._pdf_to_proyecto(doc, doc.get("origen", "ordenanzas_web")))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_urbana"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "pbom": sum(1 for r in rows if r.get("origen") == "pbom_portal"),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "ordenanzas_web"),
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
