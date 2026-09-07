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

WEB_BASE = "https://www.arahal.es"
SEDE_BASE = "https://sede.arahal.es"
NUEVOPLAN_BASE = "https://arahal.nuevoplan.es"
NUEVOSPLANES_BASE = "https://www.nuevosplanes.arahal.org"
MUNICIPIO = "Arahal"
ID_PREFIX = "arahal"
INE_CODE = "41005"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
CONSULTA_PREVIA_URL = (
    f"{WEB_BASE}/es/ayuntamiento/consulta-previa-publica-de-ordenanzas-y-reglamentos/"
)
PGOU_URL = f"{WEB_BASE}/es/ayuntamiento/pgou"
URBANISMO_URL = f"{WEB_BASE}/es/temas/urbanismo/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
LICYTAL_URL = (
    "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4101100H"
)

URBANISMO_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WEB_BASE}/es/temas/urbanismo/nivel-de-proteccion-de-inmuebles/",
    f"{WEB_BASE}/es/temas/urbanismo/fondos-europeos/",
    f"{WEB_BASE}/es/temas/urbanismo/ayudas-y-subvenciones/",
    PGOU_URL,
    f"{WEB_BASE}/nuevosplanes/index.html",
    NUEVOSPLANES_BASE + "/",
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
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|regularizaci[oó]n|nnss|catalogo|catálogo|consulta p[uú]blica|avance|"
    r"pepch|plan especial|protecci[oó]n|inspecci[oó]n.*suelo)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"elecciones|presupuesto municipal|pleno)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|potaus|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|nnss|catalogo|catálogo|regularizaci[oó]n|pepch)",
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
        "ANUNCIO PERSONAL",
        "ANUNCIO ELECCIONES",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_DRIVE = re.compile(
    r"https://drive\.google\.com/file/d/[A-Za-z0-9_-]+/view[^\"\s<>]*",
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
    if "consulta" in blob and ("previa" in blob or "pública" in blob or "publica" in blob):
        return "consulta previa"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "plan especial" in blob or "pepch" in blob:
        return "plan especial"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pgom" in blob or "pgou" in blob or "plan general" in blob or "planeamiento" in blob:
        return "PGOU"
    if "catalogo" in blob or "catálogo" in blob:
        return "planeamiento"
    if "memoria" in blob or "normas urban" in blob:
        return "planeamiento"
    return "urbanismo"


class ArahalAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS web + sede INPRO tablón + consulta previa + nuevoplan PGOM (Sevilla)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.consulta_previa_url = str(
            self.config.get("consulta_previa_url") or CONSULTA_PREVIA_URL
        )
        self.nuevoplan_base = str(self.config.get("nuevoplan_base") or NUEVOPLAN_BASE).rstrip("/")
        self.nuevosplanes_base = str(
            self.config.get("nuevosplanes_base") or NUEVOSPLANES_BASE
        ).rstrip("/")
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-arahal/1.0")},
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
            self._fetch(self.tablon_url, encoding="latin-1")
        except urllib.error.URLError:
            return []

        data = urllib.parse.urlencode(
            {
                "entidadSeleccionada": INE_CODE,
                "codigoAsuntoBusqueda": "",
                "cmd": "ANUN00",
                "opcionMenuIzda": "1",
            }
        ).encode("latin-1")
        req = urllib.request.Request(
            f"{self.sede_base}/tablon-1.0/do/anuncio/listado",
            data=data,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-arahal/1.0"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with self._opener.open(req, timeout=60) as resp:
                html = resp.read().decode("latin-1", errors="replace")
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
            low_href = href.lower()
            if ".pdf" not in low_href and "galleries" not in low_href:
                continue
            if not title or title.lower() in ("leer más", "leer mas", "consulta"):
                title = href.rsplit("/", 1)[-1][:120]
            url = _abs_url(href, base)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": title[:500], "url": url, "page": page_url})
        return rows

    def _collect_consulta_previa(self) -> list[dict[str, Any]]:
        return self._collect_pdf_links(self.consulta_previa_url, self.web_base)

    def _collect_nuevoplan_media(self) -> list[dict[str, Any]]:
        api = f"{self.nuevoplan_base}/wp-json/wp/v2/media?per_page=100"
        try:
            raw = self._fetch(api)
            items = json.loads(raw)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        rows: list[dict[str, Any]] = []
        for item in items:
            url = item.get("source_url") or ""
            if not url:
                continue
            title = (
                (item.get("title") or {}).get("rendered")
                or item.get("slug")
                or url.rsplit("/", 1)[-1]
            )
            rows.append(
                {
                    "titulo": _strip_html(title)[:500],
                    "url": url,
                    "page": f"{self.nuevoplan_base}/documentos/",
                    "origen": "nuevoplan_pgom",
                }
            )
        return rows

    def _collect_nuevosplanes_drive(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.nuevosplanes_base + "/")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in RE_DRIVE.findall(html):
            key = url.split("/d/")[1].split("/")[0] if "/d/" in url else url
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": f"Documento planeamiento (Google Drive {key[:12]})",
                    "url": url.split("?")[0],
                    "page": self.nuevosplanes_base + "/",
                    "origen": "nuevosplanes_drive",
                }
            )
        return rows

    def _collect_urbanismo_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in URBANISMO_PAGES:
            for doc in self._collect_pdf_links(page, self.web_base):
                if doc["url"] in seen:
                    continue
                seen.add(doc["url"])
                doc = dict(doc)
                doc["origen"] = "urbanismo_web"
                rows.append(doc)
        return rows

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto in (
            "PLANEAMIENTO URBANÍSTICO",
            "PLANEAMIENTO URBANISTICO",
            "ORDENANZAS",
            "ANUNCIO LICENCIAS DE APERTURAS ESTABLECIMIENTOS",
        ):
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico INPRO",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de edictos — sede.arahal.es (INE 41005)",
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
                "titulo": "Sede electrónica — trámites y carpeta ciudadana",
                "url": f"{self.sede_base}/opencms/sede/index.html",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", LICYTAL_URL),
                "fecha_concesion": None,
                "tipo": "consulta licencias Diputación (LicytalPub)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal LicytalPub — licencias publicadas Diputación Sevilla",
                "url": LICYTAL_URL,
                "source": "ayuntamiento",
                "origen": "dipusevilla_licytal",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "información trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — web municipal",
                "url": URBANISMO_URL,
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
                if r.get("origen")
                in ("sede_tablon", "sede_tramite", "dipusevilla_licytal", "web_urbanismo")
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
        for doc in self._collect_consulta_previa():
            add(self._doc_to_proyecto(doc, "consulta_previa"))
        for doc in self._collect_nuevoplan_media():
            add(self._doc_to_proyecto(doc, doc.get("origen", "nuevoplan_pgom")))
        for doc in self._collect_nuevosplanes_drive():
            add(self._doc_to_proyecto(doc, "nuevosplanes_drive"))
        for doc in self._collect_urbanismo_pages():
            add(self._doc_to_proyecto(doc, doc.get("origen", "urbanismo_web")))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento general — consulta SITUA (Junta de Andalucía)",
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
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "consulta_previa": sum(1 for r in rows if r.get("origen") == "consulta_previa"),
            "nuevoplan": sum(1 for r in rows if r.get("origen") == "nuevoplan_pgom"),
            "nuevosplanes": sum(1 for r in rows if r.get("origen") == "nuevosplanes_drive"),
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
