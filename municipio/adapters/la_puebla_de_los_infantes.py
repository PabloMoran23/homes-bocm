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

WEB_BASE = "https://www.lapuebladelosinfantes.es"
SEDE_BASE = "https://sede.lapuebladelosinfantes.es"
MUNICIPIO = "La Puebla de los Infantes"
ID_PREFIX = "la-puebla-de-los-infantes"
INE_CODE = "41078"

TABLON_URL = f"{SEDE_BASE}/tablon-1.0/do/entradaPublica?ine={INE_CODE}"
TRANSPARENCIA_URL = f"{WEB_BASE}/es/transparencia"
NOTICIAS_URL = f"{WEB_BASE}/es/actualidad/noticias/"

DEFAULT_SEED_PAGES: list[str] = [
    WEB_BASE + "/es/",
    NOTICIAS_URL,
    TRANSPARENCIA_URL,
    f"{SEDE_BASE}/opencms/system/modules/sede/elements/secciones/index",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|asimilado|fuera de ordenaci[oó]n|consulta p[uú]blica|normativa urban|"
    r"gesti[oó]n urban)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|proceso selectivo|bolsa de empleo|"
    r"subvenci[oó]n|convocatoria.*empleo|modificaci[oó]n de cr[eé]ditos|presupuesto|"
    r"protocolo|honores|distinciones|tanatorio|cementerio|feria|festej)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|licencia|sector|ordenanza|asimilado|"
    r"fuera de ordenaci[oó]n|consulta p[uú]blica)",
)
NON_URBAN_ASUNTOS = frozenset(
    {
        "RRHH",
        "EMPLEO",
        "SUBVENCIONES",
        "MODIFICACIÓN PRESUPUESTARIA",
        "CONVOCATORIA DE PLENO",
        "PRESUPUESTO MUNICIPAL",
        "FERIAS Y FESTEJOS",
        "IMPUESTOS Y TASAS",
    }
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_ROW = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>', re.I | re.S)
RE_NOTICIA_LINK = re.compile(
    r'href="(/es/actualidad/noticias/[A-Za-z0-9\-]+/?)(?:\?[^"]*)?"',
    re.I,
)
RE_TRANSPARENCIA_INDICADOR = re.compile(
    r'href="(/es/transparencia/indicadores-de-transparencia/indicador/[^"]+)"',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)


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
    m = re.search(r"/(\d{4})(\d{2})(\d{2})_", f"{text} {url}")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
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
    if "asimilado" in blob or "fuera de ordenaci" in blob:
        return "ordenanza urbanística"
    if "consulta" in blob and "pública" in blob or "consulta publica" in blob:
        return "información pública"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "convenio" in blob and "urban" in blob:
        return "convenio urbanístico"
    return "urbanismo"


class LaPueblaDeLosInfantesAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCMS web + sede GSede INPRO (tablón tablon-1.0) — Sevilla/Andalucía."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transparencia_url = str(
            self.config.get("transparencia_url") or TRANSPARENCIA_URL
        )
        self.noticias_url = str(self.config.get("noticias_url") or NOTICIAS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", False):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        encoding: str | None = None,
    ) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
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

        m = re.search(r'action="([^"]*listado[^"]*)"', html)
        if not m:
            return self._parse_tablon_html(html)

        action = _abs_url(m.group(1), self.sede_base)
        all_rows: list[dict[str, Any]] = []
        seen_refs: set[str] = set()

        for opcion in ("", "5", "1"):
            data = urllib.parse.urlencode(
                {
                    "ine": INE_CODE,
                    "cmd": "ANUN00",
                    "opcionMenuIzda": opcion,
                    "resumenBusqueda": "",
                }
            ).encode("latin-1")
            try:
                page_html = self._fetch(action, data=data, encoding="latin-1")
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_html(page_html):
                ref = row.get("referencia") or row["url"]
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
                all_rows.append(row)

        pages = {1}
        for pm in re.finditer(r"d-16544-p=(\d+)", html):
            pages.add(int(pm.group(1)))
        for page in sorted(pages):
            if page == 1:
                continue
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

    def _collect_noticia_urls(self) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for seed in self.seed_pages + [self.noticias_url]:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_NOTICIA_LINK.finditer(html):
                path = m.group(1).rstrip("/") + "/"
                if path in seen or path.endswith("/noticias/"):
                    continue
                seen.add(path)
                urls.append(_abs_url(path, self.web_base))
        return urls

    def _collect_noticias_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self._collect_noticia_urls():
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = RE_TITLE.search(html)
            titulo = _strip_html(title_m.group(1)) if title_m else page_url
            blob = f"{titulo} {page_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            if RE_TABLON_NON_URBAN.search(blob) and not RE_TABLON_URBAN.search(blob):
                continue

            fecha = _fecha_from_blob(titulo, page_url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": page_url,
                    "fecha": fecha,
                    "origen": "noticia_web",
                    "blob": blob,
                }
            )
            for pdf_href in RE_PDF.findall(html):
                pdf_url = _abs_url(pdf_href, self.web_base)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                pdf_title = titulo
                if "ANUNCIO" in pdf_href.upper():
                    pdf_title = f"{titulo} — anuncio BOP/PDF"
                elif "Ordenanza" in pdf_href or "ordenanza" in pdf_href.lower():
                    pdf_title = f"{titulo} — texto ordenanza"
                rows.append(
                    {
                        "titulo": pdf_title[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(pdf_title, pdf_url),
                        "origen": "noticia_pdf",
                        "blob": f"{pdf_title} {pdf_url}",
                    }
                )
        return rows

    def _collect_transparencia_indicadores(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparencia_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSPARENCIA_INDICADOR.finditer(html):
            path = m.group(1)
            low = path.lower()
            if not any(
                k in low
                for k in (
                    "pgou",
                    "urban",
                    "ordenacion",
                    "convenio",
                    "normativa",
                    "modificaciones-aprobadas",
                    "obrasurbanismoeinfra",
                )
            ):
                continue
            url = _abs_url(path, self.web_base)
            if url in seen:
                continue
            seen.add(url)
            slug_part = path.rstrip("/").split("/")[-1]
            titulo = slug_part.replace("-00049", "").replace("-", " ")[:500]
            rows.append(
                {
                    "titulo": f"Transparencia ITA — {titulo}",
                    "url": url,
                    "fecha": None,
                    "origen": "transparencia_indicador",
                    "blob": f"{titulo} transparencia urbanismo PGOU",
                }
            )
        return rows

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        asunto = (row.get("asunto") or "").strip().upper()
        if asunto in NON_URBAN_ASUNTOS or RE_TABLON_NON_URBAN.search(blob):
            return False
        if asunto == "URBANISMO":
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
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_TABLON_URBAN.search(blob) and (row.get("asunto") or "").upper() != "URBANISMO":
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
        return {
            "id": _stable_id("proy", doc["url"]),
            "municipio": MUNICIPIO,
            "titulo": doc["titulo"],
            "fecha": doc.get("fecha"),
            "tipo": _proyecto_tipo(doc["titulo"], doc["url"]),
            "url": doc["url"],
            "source": "ayuntamiento",
            "origen": doc.get("origen", "web"),
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
                "id": _stable_id("lic", f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — área Urbanismo (ticket GSede)",
                "url": f"{self.sede_base}/opencms/system/modules/sede/elements/secciones/index",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transparencia_url),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — sección Urbanismo (ITA 2014)",
                "url": self.transparencia_url,
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
        for doc in self._collect_noticias_urbanismo():
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_transparencia_indicadores():
            add(self._doc_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_inpro"),
            "noticias": sum(
                1 for r in rows if r.get("origen") in ("noticia_web", "noticia_pdf")
            ),
            "transparencia": sum(
                1 for r in rows if r.get("origen") == "transparencia_indicador"
            ),
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
