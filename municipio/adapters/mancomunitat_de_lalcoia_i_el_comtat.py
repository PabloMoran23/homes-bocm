from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://lamancomunitat.org"
MUNICIPIO = "Mancomunitat de L'Alcoià i El Comtat"
ID_PREFIX = "mancomunitat-de-lalcoia-i-el-comtat"

SEED_PAGES: list[tuple[str, str]] = [
    (f"{BASE}/xarxa-xaloc/", "Xarxa Xaloc — ayudas vivienda"),
    (f"{BASE}/transport-universitari-stu/", "Transport universitari STU"),
    (f"{BASE}/la-mancomunitat/", "La Mancomunitat"),
    (f"{BASE}/quisom/", "Qui som — estatutos y organigrama"),
    (f"{BASE}/la-mancomunitat/serveis/", "Serveis compartits"),
    (f"{BASE}/la-mancomunitat/municipis-mancomunitat-alcoia-comtat/", "Municipis"),
    (f"{BASE}/novaterra/", "Novaterra — desenvolupament local"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estrat[eè]gic)|pgou|plano|plànol|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"agenda urbana|ordenanza|ordenança|estatut|consulta p[uú]blica|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reglament|territori|vivienda|habitatge|"
    r"convocat|dogv|verdea|novaterra|desenvolupament)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(igualtat|joventut|serveis socials|viol[eè]ncia de g[eè]nere|protocol|"
    r"ling[uü][ií]stic|targeta|tarifes|nfc|duplicat|contacontes|senderisme|"
    r"cicloturisme|concert|emprenedor|concurs empres|protecci[oó] animal|"
    r"transport universitari.*tarif|stu\+.*tarif)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[/_-](\d{1,2})[/_-](\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_IN_PAGE = re.compile(
    r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>',
    re.I | re.S,
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _pdf_title(url: str, link_text: str = "") -> str:
    if link_text and len(link_text.strip()) > 5:
        return link_text.strip()
    name = urllib.parse.unquote(url.split("/")[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("%20", " ").replace("_", " ")
    return unescape(name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "dogv" in b or "convocat" in b:
        return "convocatoria DOGV"
    if "vivienda" in b or "habitatge" in b:
        return "ayudas vivienda"
    if "verdea" in b:
        return "plan VERDEA"
    if "estatut" in b:
        return "estatutos"
    if "novaterra" in b or "desenvolupament" in b:
        return "desarrollo local"
    if "plano" in b or "plànol" in b:
        return "plano / cartografía"
    if "reglament" in b:
        return "reglamento"
    return "normativa / planeamiento"


def _is_urban_proyecto(blob: str) -> bool:
    if RE_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
        return False
    return bool(RE_PROYECTO.search(blob))


class MancomunitatDeLalcoiaIElComtatAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress — PDFs convocatorias y páginas informativas (sin expedientes urbanísticos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or BASE).rstrip("/")
        self.seed_pages = list(self.config.get("seed_pages") or SEED_PAGES)
        self._sitemap_pages: list[str] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(self.web_base + "/", href))

    def _sitemap_urls(self) -> list[str]:
        if self._sitemap_pages is not None:
            return self._sitemap_pages
        pages: list[str] = []
        try:
            xml = self._fetch(f"{self.web_base}/page-sitemap.xml")
            root = ET.fromstring(xml)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            pages = [e.text for e in root.findall(".//sm:loc", ns) if e.text]
        except (urllib.error.URLError, ET.ParseError):
            pages = [url for url, _ in self.seed_pages]
        self._sitemap_pages = pages
        return pages

    def _collect_pdf_links(self, page_url: str, page_label: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for m in RE_PDF_IN_PAGE.finditer(html):
            href = m.group(1)
            link_text = _strip_html(m.group(2))
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            title = _pdf_title(url, link_text)
            blob = f"{title} {link_text} {page_label} {url}"
            if not _is_urban_proyecto(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": _fecha_from_blob(blob),
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob,
                    "origen": page_label,
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        crawl_pages = list(self.seed_pages)
        for page_url in self._sitemap_urls():
            if not any(page_url == u for u, _ in crawl_pages):
                crawl_pages.append((page_url, "sitemap"))

        for page_url, page_label in crawl_pages:
            for item in self._collect_pdf_links(page_url, page_label):
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)

        info_pages = [
            (f"{self.web_base}/quisom/", "Qui som — estatutos y organigrama de la mancomunitat"),
            (f"{self.web_base}/la-mancomunitat/", "La Mancomunitat — entidad supramunicipal Alcoià-Comtat"),
            (f"{self.web_base}/xarxa-xaloc/", "Xarxa Xaloc — convocatorias vivienda y desarrollo"),
        ]
        for url, titulo in info_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": None,
                    "tipo": "página informativa",
                    "blob": titulo,
                    "origen": "portal_html",
                }
            )
        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.web_base}/la-mancomunitat/serveis/"),
                "fecha_concesion": None,
                "tipo": "servicios compartidos",
                "distrito": "Alcoià i El Comtat",
                "lat": None,
                "lon": None,
                "titulo": "Serveis — catálogo servicios mancomunitat",
                "url": f"{self.web_base}/la-mancomunitat/serveis/",
                "source": "ayuntamiento",
                "nota": "Sin licencias de obra; servicios compartidos (transporte, turismo, cultura)",
            },
            {
                "id": _stable_id("lic", "sede-indeterminada"),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": "Alcoià i El Comtat",
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica (no configurada)",
                "url": "https://mancomunitatalcoiaicomtat.sedelectronica.es/",
                "source": "ayuntamiento",
                "nota": "Sede indeterminada; sin tablón ni dossier urbanismo",
            },
        ]

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

    def _proyecto_rows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self._collect_proyectos():
            key = item["url"]
            out.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"],
                    "fecha": item.get("fecha"),
                    "tipo": item.get("tipo") or "normativa",
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": item.get("origen"),
                }
            )
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_info()
        n = self._write_jsonl(out_jsonl, rows)
        return {"rows": n, "source": "portal_tramites", "at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._proyecto_rows()
        n = self._write_jsonl(out_jsonl, rows)
        return {"rows": n, "source": "portal_normativa", "at": datetime.now(timezone.utc).isoformat()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
