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

WEB_BASE = "https://www.arona.org"
SEDE_BASE = "https://sede.arona.org"
STA_BASE = "https://sta.arona.org"
MUNICIPIO = "Arona"
ID_PREFIX = "arona"

TABLON_URL = f"{STA_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON"
URBANISMO_TRAMITES_URL = f"{WEB_BASE}/Areas-Municipales/Urbanismo/Tramites"

DEFAULT_SEED_PATHS: list[str] = [
    "/Areas-Municipales/Urbanismo",
    "/Areas-Municipales/Urbanismo/Convenios-urbanisticos",
    "/Areas-Municipales/Urbanismo/Proyectos-de-urbanizaci%C3%B3n",
    "/Areas-Municipales/Urbanismo/Instrumentos-de-planeamiento-urbanistico",
    "/Areas-Municipales/Urbanismo/Plan-Especial-de-Ordenacion-del-Puerto-de-Las-Galletas",
    "/Areas-Municipales/Urbanismo/Consulta-Publica-Plan-General",
    "/Areas-Municipales/Urbanismo/Plan-General-de-Ordenacion-Urbana-1992/PGOU",
    "/Areas-Municipales/Urbanismo/Historicos-PGOU/Convenios-Urbanisticos",
    "/Areas-Municipales/Urbanismo/Noticias",
    "/Areas-Municipales/Urbanismo/Proyecto-URBAN-2007-2013",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|actividad (?:inocua|clasificada|comercial))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|suelo|"
    r"cambio de uso|anuncio bop|anuncio boc|exposici[oó]n|reglamento org[aá]nico|"
    r"urbanizaci[oó]n|instrumento|sentencia|ejecuci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(indicadores sobre urbanismo|indicadores de urbanismo|ayuda en pdf|"
    r"proceso selectivo|empleo p[uú]blico|tajaraste|v[ií]deo:|\.mp3|\.avi|\.tif\b)",
)
RE_DOC_HREF = re.compile(
    r'href="([^"]+(?:\.pdf|/Portals/0/(?:documentos|adjuntos)/|/RecursosWeb/DOCUMENTOS/)[^"]*)"',
    re.I,
)
RE_NEWS_LINK = re.compile(
    r'href="(/Areas-Municipales/Urbanismo/Noticias/ctl/Ver/[^"]+)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="((?:https://www\.arona\.org)?/Tramites/ctl/Ver/[^"]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_FILE = re.compile(r"(?:^|/)(\d{8})_\d+")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_FILE.search(url or "")
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    return _fecha_from_url(url)


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str) -> str:
    blob = title.lower()
    if "plan especial" in blob:
        return "plan especial"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "proyecto de urbanizaci" in blob or "urbanizaci" in blob:
        return "proyecto urbanización"
    if "estudio ambiental" in blob:
        return "evaluación ambiental"
    if "licencia" in blob:
        return "licencia publicada"
    if "anuncio" in blob or "exposici" in blob:
        return "información pública"
    if "plano" in blob:
        return "planeamiento"
    return "urbanismo"


class AronaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal DNN (urbanismo/PDFs) + sede STA tablón + trámites urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sta_base = str(self.config.get("sta_base") or STA_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_paths = [str(p) for p in (self.config.get("seed_paths") or DEFAULT_SEED_PATHS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-arona/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sta.arona.org" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(self.web_base + "/", href))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows = self._extract_sta_dataset(html, "TABLON")
        if not rows:
            rows = self._extract_sta_dataset(html, "PTS2_TABLON")
        return rows

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, fecha, url

    def _extract_link_title(self, html: str, href: str) -> str:
        pattern = re.compile(
            rf'href="{re.escape(href)}"[^>]*>(.*?)</a>',
            re.I | re.S,
        )
        m = pattern.search(html)
        if m:
            title = _strip_html(m.group(1))
            if title and title.lower() not in {"description", "ver", "descargar"}:
                return title[:500]
        return unescape(Path(urllib.parse.unquote(href.split("?")[0])).name)[:500]

    def _crawl_urbanismo_documents(self) -> list[dict[str, Any]]:
        visited_pages: set[str] = set()
        queue = [self._abs_url(p) for p in self.seed_paths]
        records: list[dict[str, Any]] = []
        seen_docs: set[str] = set()

        while queue and len(visited_pages) < 45:
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue

            title_m = re.search(r"<title[^>]*>([^<|]+)", html)
            page_title = unescape(title_m.group(1).strip()) if title_m else page_url

            for m in RE_NEWS_LINK.finditer(html):
                news_url = self._abs_url(m.group(1))
                if news_url not in visited_pages and news_url not in queue:
                    queue.append(news_url)

            for m in re.finditer(r'href="([^"]+)"', html):
                href = m.group(1)
                if "/Areas-Municipales/Urbanismo" in href and not href.startswith("#"):
                    sub = self._abs_url(href.split("#")[0])
                    if sub not in visited_pages and sub not in queue:
                        queue.append(sub)

            for m in RE_DOC_HREF.finditer(html):
                href = unescape(m.group(1))
                doc_url = self._abs_url(href.split("?")[0])
                if doc_url in seen_docs:
                    continue
                seen_docs.add(doc_url)
                titulo = self._extract_link_title(html, href)
                if not titulo or RE_NOISE.search(titulo) or RE_NOISE.search(doc_url):
                    continue
                records.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(titulo, doc_url),
                        "url": page_url,
                        "pdf_url": doc_url,
                        "page_title": page_title,
                    }
                )

            for m in RE_NEWS_LINK.finditer(html):
                news_url = self._abs_url(m.group(1))
                if news_url in seen_docs:
                    continue
                seen_docs.add(news_url)
                try:
                    news_html = self._fetch(news_url)
                except (urllib.error.URLError, TimeoutError, OSError):
                    continue
                h1 = re.search(r"<h1[^>]*>([^<]+)", news_html)
                titulo = unescape(h1.group(1).strip()) if h1 else news_url
                records.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(news_html, news_url),
                        "url": news_url,
                        "pdf_url": None,
                        "page_title": "Noticias Urbanismo",
                    }
                )

        return records

    def _collect_tramites_licencia(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (URBANISMO_TRAMITES_URL, f"{self.web_base}/Tramites"):
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in RE_TRAMITE_LINK.finditer(html):
                href = m.group(1)
                url = self._abs_url(href)
                if url in seen:
                    continue
                titulo = self._extract_link_title(html, href)
                if not RE_LICENCIA.search(titulo):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": titulo[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Trámite informativo DNN/sede; sin listado de concesiones",
                    }
                )
        return rows

    def _title_to_licencia(self, title: str, url: str, fecha: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }

    def _doc_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any] | None:
        titulo = doc["titulo"]
        url = doc.get("pdf_url") or doc["url"]
        if RE_NOISE.search(titulo) or RE_NOISE.search(url):
            return None
        if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(doc.get("page_title", "")):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": doc.get("fecha") or None,
            "tipo": _proyecto_tipo(titulo),
            "url": doc.get("url") or url,
            "source": "ayuntamiento",
            "origen": doc.get("page_title"),
        }
        if doc.get("pdf_url"):
            rec["pdf_url"] = doc["pdf_url"]
        return rec

    def _title_to_proyecto(self, title: str, url: str, fecha: str) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_tramites_licencia():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramites": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec:
                existing[rec["id"]] = rec

        for rec in self._collect_tramites_licencia():
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
            title, fecha, url = self._tablon_row_to_record(item)
            add(self._title_to_proyecto(title, url, fecha))

        for doc in self._crawl_urbanismo_documents():
            add(self._doc_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_attempted": True,
            "seed_pages": len(self.seed_paths),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
