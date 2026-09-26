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

WEB_BASE = "https://bollullosdelamitacion.org"
SEDE_BASE = "https://sede.bollullosdelamitacion.es"
MUNICIPIO = "Bollullos de la Mitación"
ID_PREFIX = "bollullos-de-la-mitacion"
INE_CODE = "41016"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
URBANISMO_DOCS_URL = f"{WEB_BASE}/tr/08-urbanismo-y-obras-publicas/urbanismo-documentos"
PGOU_URL = f"{WEB_BASE}/index.php/delegaciones-bollullos/delegacion-de-urbanismo/pgou"
NORMATIVA_URL = f"{WEB_BASE}/tr/09-normativa-y-acuerdos-municipales/normativa"
PMUS_PDF_URL = f"{WEB_BASE}/images/delegaciones/PersonalUrbanismo/PMUS/PMVSBollullos.pdf"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|municipal)|pgou|pgom|pibo|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|actuaci[oó]n|urbanizaci[oó]n|innovaci[oó]n|pmus|pmvs)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"activat joven|limpiador|auxiliar administrativo|jurado|cobranza|iae|ibi|"
    r"inmatriculaci[oó]n comercio|certificado urban[ií]stico)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pibo|nnss|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance|actuaci[oó]n|urbanizaci[oó]n|innovaci[oó]n|estudio de detalle|"
    r"reparcel|autorizaci[oó]n adva|infraestructura el[eé]ctrica|generaci[oó]n de energ[ií]a)",
)
URBAN_ASUNTOS = frozenset(
    {
        "URBANISMO",
        "PLANEAMIENTO URBANÍSTICO",
        "PLANEAMIENTO URBANISTICO",
        "ORDENANZAS",
    }
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "PERSONAL",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "ELECCIONES",
        "ORGANIZACIÓN MUNICIPAL",
        "BANDOS",
        "INFORMACION",
        "PUBLICACIONES BOP/BOE",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_DOC_SECTION = re.compile(
    r'<strong>\s*(\d{1,2}/\d{1,2}/\d{4})\s+(.*?)</strong>(.*?)(?=<strong>|$)',
    re.I | re.S,
)
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
    href = unescape(href).strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href.replace("https://images//", f"{WEB_BASE}/images/")
    return urllib.parse.urljoin(base, href)


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "estudio de detalle" in blob or "estudio de ordenaci" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or "sector" in blob or "p.p." in blob:
        return "plan parcial"
    if "innovaci" in blob and "nnss" in blob:
        return "innovación NNSS"
    if "reparcel" in blob:
        return "reparcelación"
    if "urbanizaci" in blob:
        return "urbanización"
    if "actuaci" in blob and "extraordinaria" in blob:
        return "actuación extraordinaria"
    if "consulta" in blob and "pública" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgou" in blob or "pgom" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "pmus" in blob or "pmvs" in blob:
        return "PMUS"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    return "urbanismo"


class BollullosDeLaMitacionAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla web + GSede sede + tablón INPRO (INE 41016)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.urbanismo_docs_url = str(
            self.config.get("urbanismo_docs_url") or URBANISMO_DOCS_URL
        )
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.pmus_pdf_url = str(self.config.get("pmus_pdf_url") or PMUS_PDF_URL)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-bollullos/1.0")},
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

    def _collect_pdf_links(self, page_url: str, base: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title or title.lower() in ("leer más", "leer mas"):
                continue
            low_href = href.lower()
            if ".pdf" not in low_href and "documentos/" not in low_href:
                continue
            url = _abs_url(href, base)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": title[:500], "url": url, "page": page_url})
        return rows

    def _collect_urbanismo_documentos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_docs_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOC_SECTION.finditer(html):
            fecha_raw, title_html, body = m.group(1), m.group(2), m.group(3)
            titulo = _strip_html(title_html).strip(" :")
            if not titulo or len(titulo) < 8:
                continue
            blob = f"{titulo} {fecha_raw}"
            if not RE_PROYECTO.search(blob):
                continue
            pdf_match = RE_PDF_HREF.search(body)
            if not pdf_match:
                continue
            url = _abs_url(pdf_match.group(1), self.web_base)
            key = f"{fecha_raw}:{titulo[:120]}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "origen": "urbanismo_documentos",
                }
            )
        return rows

    def _collect_pgou_documents(self) -> list[dict[str, Any]]:
        docs = self._collect_pdf_links(self.pgou_url, self.web_base)
        docs.append(
            {
                "titulo": "Plan Municipal de Vivienda y Suelo (PMUS) Bollullos de la Mitación",
                "url": self.pmus_pdf_url,
                "page": self.pgou_url,
            }
        )
        return docs

    def _collect_normativa_urbana(self) -> list[dict[str, Any]]:
        docs = self._collect_pdf_links(self.normativa_url, self.web_base)
        out: list[dict[str, Any]] = []
        for doc in docs:
            blob = f"{doc['titulo']} {doc['url']}"
            if RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob):
                doc = dict(doc)
                doc["origen"] = "normativa_urbana"
                out.append(doc)
        return out

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in URBAN_ASUNTOS:
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
        if not RE_TABLON_URBAN.search(blob) and asunto not in URBAN_ASUNTOS:
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
        origen = doc.get("origen", "urbanismo_documentos")
        key = f"{doc.get('fecha') or ''}:{titulo}"
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": doc.get("fecha") or _fecha_from_blob(titulo, url),
            "tipo": _proyecto_tipo(titulo, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
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
                "titulo": "Tablón electrónico INPRO — sede municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — área Urbanismo (ticket GSede)",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_docs_url),
                "fecha_concesion": None,
                "tipo": "documentos urbanísticos en información pública",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Documentos urbanísticos — exposición pública",
                "url": self.urbanismo_docs_url,
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
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_urbanismo")
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
        for doc in self._collect_urbanismo_documentos():
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_pgou_documents():
            add(self._pdf_to_proyecto(doc, "pgou_web"))
        for doc in self._collect_normativa_urbana():
            add(self._pdf_to_proyecto(doc, doc.get("origen", "normativa_urbana")))
        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "NNSS/PGOM Bollullos de la Mitación — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "planeamiento SITUA",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "urbanismo_documentos": sum(
                1 for r in rows if r.get("origen") == "urbanismo_documentos"
            ),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_web"),
            "normativa": sum(1 for r in rows if r.get("origen") == "normativa_urbana"),
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
