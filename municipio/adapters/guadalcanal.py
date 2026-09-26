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

WEB_BASE = "https://www.guadalcanal.es"
SEDE_BASE = "https://sede.guadalcanal.es"
TRANSPARENCIA_BASE = "https://transparencia.guadalcanal.es"
MUNICIPIO = "Guadalcanal"
ID_PREFIX = "guadalcanal"
# La sede usa INE 41048 (coincide con CIF P4104800J); INE oficial INE.es = 41049.
INE_CODE = "41048"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
PGOU_TRANSPARENCIA_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00017/"
)
MODIFICACIONES_PGOU_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00017/"
)
NORMATIVA_TRANSPARENCIA_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "83.Se-publica-la-Normativa-municipal-tanto-del-Ayuntamiento-como-de-los-Entes-"
    "instrumentales-Relacion-de-normativa-en-curso-Ordenanzas-y-texto-en-version-"
    "inicial-memorias-e-informes-de-elaboracion-de-las-normativas./"
)
LICYTAL_URL = "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4104800J"

DEFAULT_TRANSPARENCIA_PAGES: list[str] = [
    PGOU_TRANSPARENCIA_URL,
    MODIFICACIONES_PGOU_URL,
    NORMATIVA_TRANSPARENCIA_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|impuesto.*construcciones)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|consulta p[uú]blica|avance|exposici[oó]n p[uú]blica|nnss|"
    r"normas subsidiarias|catalogo|catálogo|impacto ambiental|eae)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de (?:empleo|trabajo)|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"activat joven|bando|bases de la convocatoria|lista definitiva|reapertura bolsa|"
    r"reglamento de control interno|centro de iniciativas empresariales|"
    r"acuerdo plenario|personal laboral|prestaci[oó]n de servicios|oposici[oó]n|"
    r"concurso-oposici|nombramiento|interino|funcionario)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(pgou|planeamiento|plan (?:parcial|especial|general)|"
    r"informaci[oó]n p[uú]blica|licencia de obra|sector urban|ordenanza (?:reguladora|urban)|"
    r"consulta p[uú]blica|avance del plan|estudio ambiental estrat[eé]gico|"
    r"modificaci[oó]n (?:puntual|del pgou)|normas subsidiarias|memoria de ordenaci)",
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "EMPLEO",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
        "BANDOS",
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
    if "modificaci" in blob and ("puntual" in blob or "n-2" in blob or "n2" in blob):
        return "modificación puntual PGOU"
    if "pgou" in blob or "plan general" in blob or "memoria de orden" in blob:
        return "PGOU"
    if "normas subsidiarias" in blob or "nnss" in blob or "catalogo" in blob:
        return "normas subsidiarias"
    if "estudio ambiental" in blob or "eae" in blob or "impacto ambiental" in blob:
        return "evaluación ambiental"
    if "plano" in blob or "cartograf" in blob:
        return "cartografía urbanística"
    if "exposici" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    return "urbanismo"


class GuadalcanalAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS INPRO web + GSede propia + tablón INPRO + transparencia PGOU (Sevilla/Andalucía)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transparencia_pages = [
            str(u) for u in (self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES)
        ]
        self.licytal_url = str(self.config.get("licytal_url") or LICYTAL_URL)
        self.ine_code = str(self.config.get("ine_code") or INE_CODE)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch_text(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadalcanal/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors="replace")
        if raw[:4] == b"%PDF":
            return ""
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
                    "blob": f"{asunto} {extracto}",
                    "origen": "tablon_inpro",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_text(self.tablon_url, encoding="latin-1")
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
                    f"d-16544-p={page}&ine={self.ine_code}&cmd=ANUN00&opcionMenuIzda=1"
                )
                try:
                    page_html = self._fetch_text(page_url, encoding="latin-1")
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
        seen: set[str] = set()
        for page_url in self.transparencia_pages:
            try:
                html = self._fetch_text(page_url)
            except urllib.error.URLError:
                continue
            page_slug = page_url.rstrip("/").split("/")[-1][:40]
            for href, inner in RE_LINK.findall(html):
                if ".pdf" not in href.lower():
                    continue
                title = _strip_html(inner) or href.split("/")[-1]
                url = _abs_url(href, self.transparencia_base)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url,
                        "page": page_url,
                        "page_slug": page_slug,
                        "blob": f"{title} {page_slug}",
                        "origen": "transparencia_pgou",
                    }
                )
        return rows

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in ("PLANEAMIENTO URBANÍSTICO", "PLANEAMIENTO URBANISTICO", "ORDENANZAS"):
            return True
        if asunto == "EXPOSICIÓN PÚBLICA":
            return bool(RE_TABLON_URBAN.search(blob) or RE_PROYECTO.search(blob))
        if asunto == "EMPLEO":
            return False
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
        if asunto == "EXPOSICIÓN PÚBLICA":
            if not (RE_TABLON_URBAN.search(blob) or RE_PROYECTO.search(blob)):
                return None
        elif not RE_TABLON_URBAN.search(blob) and asunto not in (
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

    def _pdf_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{doc.get('titulo', '')} {doc.get('url', '')} {doc.get('page_slug', '')}"
        if not RE_PROYECTO.search(blob):
            return None
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
            "origen": doc.get("origen", "transparencia_pgou"),
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
                "titulo": "Tablón electrónico INPRO — sede municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/opencms/sede"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo de trámites",
                "url": f"{self.sede_base}/opencms/opencms/sede",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.licytal_url),
                "fecha_concesion": None,
                "tipo": "contratación local (Licyt@l Diputación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal Licyt@l — contratación municipal (CIF P4104800J)",
                "url": self.licytal_url,
                "source": "ayuntamiento",
                "origen": "licytal_info",
            },
            {
                "id": _stable_id("lic", PGOU_TRANSPARENCIA_URL),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — indicador PGOU y planos",
                "url": PGOU_TRANSPARENCIA_URL,
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
        ]

    def _pgou_index_row(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", PGOU_TRANSPARENCIA_URL),
            "municipio": MUNICIPIO,
            "titulo": "PGOU — adaptación a la LOUA (memoria, planos y normas subsidiarias)",
            "fecha": "2019-01-01",
            "tipo": "PGOU",
            "url": PGOU_TRANSPARENCIA_URL,
            "source": "ayuntamiento",
            "origen": "transparencia_pgou",
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "licytal_info", "transparencia")
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

        add(self._pgou_index_row())
        for doc in self._collect_transparencia_pdfs():
            add(self._pdf_to_proyecto(doc))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_pgou"),
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
