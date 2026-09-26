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
MUNICIPIO = "El Palmar de Troya"
ID_PREFIX = "el-palmar-de-troya"
INE_CODE = "41053"

TABLON_URL = f"{WEB_BASE}/.galleries/enlaces-generales/tablon-de-anuncios"
PGOU_URL = f"{WEB_BASE}/es/urbanismo/pgou"
PROYECTOS_OBRA_URL = f"{WEB_BASE}/es/urbanismo/proyecto-de-obras/"
URBANISMO_NEWS_URL = (
    f"{WEB_BASE}/es/busqueda/?formCategoryFilter="
    "/sites/elpalmardetroya/.categories/temas/urbanismo/&formTypeFilter=pm-noticia"
)
LICYTAL_URL = "https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4100053J"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|calificaci[oó]n.*ambiental|licitaci[oó]n.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|consulta p[uú]blica|avance|reurbaniz|guarder[ií]a|piscina|"
    r"casa del mayor|carretera|rehabilitaci[oó]n|licitaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|"
    r"cobranza.*ibi|electores|candidatos a jurado|bases por la que)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|consulta p[uú]blica|"
    r"avance del plan|exposici[oó]n p[uú]blica|edicto)",
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
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_NEWS_LINK = re.compile(r'href="(/es/actualidad/noticias/[^"]+)"', re.I)
RE_CONTENT_TITLE = re.compile(r'class="contentMainTitle"[^>]*>([^<]+)', re.I)


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
        return "PGOM/PGOU"
    if "consulta" in blob and "pública" in blob or "exposición pública" in blob:
        return "información pública"
    if "licitaci" in blob and "obra" in blob:
        return "licitación obra"
    if "reurbaniz" in blob:
        return "reurbanización"
    if "proyecto" in blob and ("obra" in blob or "av." in blob):
        return "proyecto de obra"
    if "memoria" in blob or "planos" in blob:
        return "planeamiento"
    return "urbanismo"


class ElPalmarDeTroyaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS INPRO web + tablón embebido + GSede propia (Sevilla/Andalucía)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.proyectos_obra_url = str(self.config.get("proyectos_obra_url") or PROYECTOS_OBRA_URL)
        self.urbanismo_news_url = str(self.config.get("urbanismo_news_url") or URBANISMO_NEWS_URL)
        self.licytal_url = str(self.config.get("licytal_url") or LICYTAL_URL)
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _fetch(self, url: str, encoding: str | None = None) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-palmar-de-troya/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read()

    def _fetch_text(self, url: str, encoding: str | None = None) -> str:
        raw = self._fetch(url)
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
            url = _abs_url(url_path, self.web_base)
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
                    f"{self.web_base}/tablon-1.0/do/anuncio/listado?"
                    f"d-16544-p={page}&ine={INE_CODE}&cmd=ANUN00&opcionMenuIzda=1"
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

    def _collect_pdf_links(self, page_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch_text(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            title = _strip_html(inner)
            if not title or title.lower() in ("leer más", "leer mas"):
                continue
            if ".pdf" not in href.lower():
                continue
            url = _abs_url(href, self.web_base)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": title[:500], "url": url, "page": page_url})
        return rows

    def _collect_urbanismo_news(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_text(self.urbanismo_news_url)
        except urllib.error.URLError:
            return []

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in RE_NEWS_LINK.findall(html):
            path = path.split("?", 1)[0].rstrip("/") + "/"
            if path in seen:
                continue
            seen.add(path)
            url = _abs_url(path, self.web_base)
            try:
                article_html = self._fetch_text(url)
            except urllib.error.URLError:
                continue
            title_m = RE_CONTENT_TITLE.search(article_html)
            title = _strip_html(title_m.group(1)) if title_m else path.split("/")[-2]
            fecha = _parse_fecha_dmy(article_html)
            pdfs = [
                _abs_url(h, self.web_base)
                for h in re.findall(r'href="([^"]+)"', article_html)
                if ".pdf" in h.lower()
            ]
            out.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": fecha,
                    "pdfs": pdfs,
                    "blob": title,
                    "origen": "noticia_urbanismo",
                }
            )
        return out

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico INPRO — web municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede GSede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo de trámites",
                "url": f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index",
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
                "titulo": "Portal Licyt@l — contratación municipal (CIF P4100053J)",
                "url": self.licytal_url,
                "source": "ayuntamiento",
                "origen": "licytal_info",
            },
        ]

    def _news_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = item["url"]
        pdf_url = item["pdfs"][0] if item.get("pdfs") else item["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia / calificación ambiental",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": pdf_url,
            "source": "ayuntamiento",
            "origen": item.get("origen", "noticia_urbanismo"),
        }

    def _news_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = item["url"]
        pdf_url = item["pdfs"][0] if item.get("pdfs") else item["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item["titulo"], item["url"]),
            "url": pdf_url,
            "source": "ayuntamiento",
            "origen": item.get("origen", "noticia_urbanismo"),
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

    def _pgou_row(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.pgou_url),
            "municipio": MUNICIPIO,
            "titulo": "PGOU / PGOM — documentación urbanismo (PDF)",
            "fecha": "2024-01-01",
            "tipo": "PGOM/PGOU",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "pgou_web",
            "nota": "Municipio en redacción del primer PGOM; página sirve PDF directo",
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
        for item in self._collect_urbanismo_news():
            rec = self._news_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "info": sum(1 for r in rows if r.get("origen") in ("web_tablon", "sede_tramite", "licytal_info")),
            "noticias": sum(1 for r in rows if r.get("origen") == "noticia_urbanismo"),
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
        for item in self._collect_urbanismo_news():
            rec = self._news_to_licencia(item)
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

        add(self._pgou_row())
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for doc in self._collect_pdf_links(self.proyectos_obra_url):
            add(self._pdf_to_proyecto(doc, "proyectos_obra"))
        for item in self._collect_urbanismo_news():
            add(self._news_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_web"),
            "proyectos_obra": sum(1 for r in rows if r.get("origen") == "proyectos_obra"),
            "noticias": sum(1 for r in rows if r.get("origen") == "noticia_urbanismo"),
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
