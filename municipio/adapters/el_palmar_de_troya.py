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

WEB_BASE = "https://www.elpalmardetroya.es"
SEDE_BASE = "https://sede.elpalmardetroya.es"
TRANSPARENCIA_BASE = "https://transparencia.elpalmardetroya.es"
MUNICIPIO = "El Palmar de Troya"
ID_PREFIX = "el-palmar-de-troya"
INE_CODE = "41996"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
PGOU_TRANSPARENCIA_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00029/"
)
NORMATIVA_TRANSPARENCIA_URL = (
    f"{TRANSPARENCIA_BASE}/es/transparencia/indicadores-de-transparencia/indicador/"
    "56.-Se-publica-informacion-precisa-de-la-normativa-vigente-en-materia-de-gestion-urbanistica-del-Ayuntamiento.-00029/"
)
URBANISMO_NOTICIAS_URL = f"{WEB_BASE}/es/urbanismo/noticias/"
PGOM_WEB_URL = "https://elpalmardetroya.nuevoplan.es/"
SITUA_URL = f"https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid={INE_CODE}"
LICENCIA_NOTICIA_URL = (
    f"{WEB_BASE}/es/actualidad/noticias/"
    "Resolucion-de-Alcaldia-n-25-de-fecha-14-de-Enero-de-2020-que-inicia-expediente-de-concesion-de-licencia-de-actividad-sometida-al-tramite-de-calificacion-ambiental./"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|calificaci[oó]n.*actividad|calificaci[oó]n.*ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|normativa urban|ordenanza|consulta p[uú]blica|avance|cartograf|"
    r"rehabilitaci[oó]n|licitaci[oó]n.*obra|obra[s]? de|inversi[oó]n.*municipal)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"cobranza|electores inscritos|jurado|emergencia social|bases por la que)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n)",
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
        "PROCESOS SELECTIVOS",
        "BASES",
        "PUBLICACIONES BOP",
        "EXPOSICION EDICTOS",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_NOTICIA_LINK = re.compile(
    r'<a href="(/es/urbanismo/noticias/[^"?#]+)[^"]*"[^>]*>([^<]+)</a>',
    re.I,
)


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
    if "pgom" in blob or "pgou" in blob or "plan general" in blob:
        return "PGOM"
    if "exposici" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "cartograf" in blob or "ordenaci" in blob or "diagn" in blob:
        return "cartografía planeamiento"
    if "memoria" in blob:
        return "memoria planeamiento"
    if "licitaci" in blob and "obra" in blob:
        return "licitación obra"
    if "rehabilitaci" in blob or "obra" in blob:
        return "obra municipal"
    if "licencia" in blob or "calificaci" in blob:
        return "licencia publicada"
    if "inversi" in blob:
        return "inversión urbanística"
    return "urbanismo"


class ElPalmarDeTroyaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS INPRO web + sede GSede propia (tablón INPRO) + transparencia PGOM."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.ine_code = str(self.config.get("ine_code") or INE_CODE)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_transparencia_url = str(
            self.config.get("pgou_transparencia_url") or PGOU_TRANSPARENCIA_URL
        )
        self.normativa_transparencia_url = str(
            self.config.get("normativa_transparencia_url") or NORMATIVA_TRANSPARENCIA_URL
        )
        self.urbanismo_noticias_url = str(
            self.config.get("urbanismo_noticias_url") or URBANISMO_NOTICIAS_URL
        )
        self.pgom_web_url = str(self.config.get("pgom_web_url") or PGOM_WEB_URL)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, *, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-palmar-de-troya/1.0")},
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
                    f"d-16544-p={page}&ine={self.ine_code}&cmd=ANUN00&opcionMenuIzda=1"
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

    def _collect_pdf_links(self, page_url: str, base: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title:
                continue
            low_href = href.lower()
            if ".pdf" not in low_href and "galleries/" not in low_href:
                continue
            url = _abs_url(href, base)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": title[:500] or url.rsplit("/", 1)[-1],
                    "url": url,
                    "page": page_url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_urbanismo_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, 12):
            url = self.urbanismo_noticias_url
            if page > 1:
                url = f"{self.urbanismo_noticias_url}index.html?page={page}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            found = 0
            for href, title in RE_NOTICIA_LINK.findall(html):
                title = re.sub(r"\s+", " ", title).strip()
                if not title or href in seen:
                    continue
                seen.add(href)
                found += 1
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": _abs_url(href, self.web_base),
                        "origen": "urbanismo_noticia",
                    }
                )
            if page > 1 and found == 0:
                break
        return rows

    def _collect_licencia_noticia_2020(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(LICENCIA_NOTICIA_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        title = "Resolución de Alcaldía nº 25 — licencia de actividad (calificación ambiental)"
        rows.append(
            {
                "id": _stable_id("lic", LICENCIA_NOTICIA_URL),
                "fecha_concesion": "2020-01-14",
                "tipo": "licencia de actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title,
                "url": LICENCIA_NOTICIA_URL,
                "source": "ayuntamiento",
                "origen": "noticia_web",
            }
        )
        for href, inner in RE_LINK.findall(html):
            t = _strip_html(inner)
            if ".pdf" in href.lower() and RE_LICENCIA.search(t):
                url = _abs_url(href, self.web_base)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": "2020-01-14",
                        "tipo": "licencia de actividad",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": t[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "noticia_pdf",
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

    def _doc_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
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
            "origen": doc.get("origen", "transparencia"),
        }

    def _noticia_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item["titulo"]
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob.replace("licencia", "")):
            return None
        url = item["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": _fecha_from_blob(item["titulo"], url),
            "tipo": _proyecto_tipo(item["titulo"], url),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen", "urbanismo_noticia"),
        }

    def _metadata_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.pgom_web_url),
                "municipio": MUNICIPIO,
                "titulo": "PGOM El Palmar de Troya — portal consulta NuevoPlan",
                "fecha": None,
                "tipo": "PGOM",
                "url": self.pgom_web_url,
                "source": "ayuntamiento",
                "origen": "pgom_web",
            },
            {
                "id": _stable_id("proy", self.situa_url),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento — consulta SITUA Junta de Andalucía",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.situa_url,
                "source": "ayuntamiento",
                "origen": "situa",
            },
        ]

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
                "tipo": "trámites urbanismo (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — área Urbanismo (ticket GSede)",
                "url": f"{self.sede_base}/opencms/opencms/sede",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/es/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "sección urbanismo web",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — web municipal",
                "url": f"{self.web_base}/es/urbanismo/",
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
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
        for rec in self._collect_licencia_noticia_2020():
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
                in ("sede_tablon", "sede_tramite", "web_urbanismo", "noticia_web", "noticia_pdf")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for rec in self._collect_licencia_noticia_2020():
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

        for rec in self._metadata_proyectos():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for doc in self._collect_pdf_links(
            self.pgou_transparencia_url, TRANSPARENCIA_BASE, "pgom_transparencia"
        ):
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_pdf_links(
            self.normativa_transparencia_url, TRANSPARENCIA_BASE, "normativa_urbana"
        ):
            add(self._doc_to_proyecto(doc))
        for item in self._collect_urbanismo_noticias():
            add(self._noticia_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "pgom": sum(1 for r in rows if r.get("origen") == "pgom_transparencia"),
            "normativa": sum(1 for r in rows if r.get("origen") == "normativa_urbana"),
            "noticias": sum(1 for r in rows if r.get("origen") == "urbanismo_noticia"),
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
