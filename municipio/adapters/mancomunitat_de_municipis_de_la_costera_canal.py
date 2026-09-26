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

WEB_BASE = "https://www.lacosteracanal.es"
SEDE_BASE = "https://lacosteracanal.sede.dival.es"
MUNICIPIO = "Mancomunitat de Municipis de la Costera-Canal"
ID_PREFIX = "mancomunitat-de-municipis-de-la-costera-canal"
URBANISMO_URL = f"{WEB_BASE}/es/transparencia/urbanismo-obras-publicas-medio-ambiente"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"

SEED_PAGES: list[tuple[str, str]] = [
    (URBANISMO_URL, "Urbanismo — PMUS y publicación BOP"),
]

# PMUS publicados en transparencia (nov 2022) — fallback si el Drupal tarda >timeout.
KNOWN_PMUS_PDFS: list[tuple[str, str]] = [
    ("/sites/www.lacosteracanal.es/files/20221114_PUBLICACI%C3%93N%20BOP.pdf", "Publicación BOP PMUS"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Barxeta_f.pdf", "PMUS Barxeta"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Cerd%C3%A0_f.pdf", "PMUS Cerdà"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_laFontdelaFiguera_f.pdf", "PMUS La Font de la Figuera"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Novetl%C3%A8_f.pdf", "PMUS Novetlè"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_LaGranjadelaCostera_f.pdf", "PMUS La Granja de la Costera"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_ElGenoves_f.pdf", "PMUS El Genovés"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_RotglaiCorbera_f.pdf", "PMUS Rotglà i Corberà"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_LlaneradeRanes_f-1.pdf", "PMUS Llanera de Ranes"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Valles_f.pdf", "PMUS Vallés"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Llocnoud%27EnFenollet_f.pdf", "PMUS Llocnou d'En Fenollet"),
    ("/sites/www.lacosteracanal.es/files/20221114_PMUS_Torrella_f.pdf", "PMUS Torrella"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estrat[eè]gic|movilidad)|pgou|pmus|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"ordenanza|estatut|consulta p[uú]blica|aprobaci[oó]n (?:inicial|definitiva)|"
    r"reglament|territori|mobilitat|movilidad|bop\b|publicaci)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(cuenta general|contabilidad|exposici[oó]n al p[uú]blico de la cuenta|"
    r"selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"protecci[oó]n de datos|reclamaci[oó]n.*consumo|instancia general|"
    r"notificaci[oó]n electr[oó]nica|quejas y sugerencias)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[/_-](\d{1,2})[/_-](\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PMUS_MUN = re.compile(r"(?i)pmus[_\s-]+(.+?)(?:_f)?\.pdf")


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
    m = RE_PMUS_MUN.search(name)
    if m:
        mun = m.group(1).replace("_", " ").replace("%20", " ").strip()
        return f"PMUS {mun}"
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("%20", " ").replace("_", " ")
    return unescape(name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pmus" in b or "movilidad" in b or "mobilitat" in b:
        return "PMUS"
    if "bop" in b and "publicaci" in b:
        return "publicación BOP"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "plan general" in b or "pgou" in b:
        return "PGOU"
    if "ordenanza" in b or "ordenança" in b:
        return "ordenanza"
    if "reglament" in b:
        return "reglamento"
    if "consulta" in b and "p" in b and "blica" in b:
        return "consulta pública"
    return "normativa / planeamiento"


def _is_urban_proyecto(blob: str) -> bool:
    if RE_NON_URBAN.search(blob):
        return False
    return bool(RE_PROYECTO.search(blob))


class MancomunitatDeMunicipisDeLaCosteraCanalAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portales + sede Dival — PMUS PDFs y tablón RSS (sin expedientes urbanísticos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.seed_pages = list(self.config.get("seed_pages") or SEED_PAGES)

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(self.web_base + "/", href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _collect_pdf_links(self, page_url: str, page_label: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.I | re.S,
        ):
            href = m.group(1)
            link_text = _strip_html(m.group(2))
            url = self._abs_web(href)
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

    def _known_pmus_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, title in KNOWN_PMUS_PDFS:
            url = self._abs_web(href)
            blob = f"{title} {url}"
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": "2022-11-14",
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob,
                    "origen": "known_pmus",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, timeout=60)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            blob = title
            if not _is_urban_proyecto(blob):
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].strip(),
                        "%a, %d %b %Y %H:%M:%S",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for page_url, page_label in self.seed_pages:
            for item in self._collect_pdf_links(page_url, page_label):
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)

        if not any(r.get("origen") not in ("portal_html",) for r in rows):
            for item in self._known_pmus_rows():
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)

        for item in self._collect_tablon_rss():
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)

        info_pages = [
            (
                f"{self.web_base}/es/transparencia/urbanismo-obras-publicas-medio-ambiente",
                "Urbanismo — PMUS comarcales (transparencia)",
            ),
            (
                self.tablon_url,
                "Tablón de anuncios — sede electrónica Costera-Canal",
            ),
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
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo de servicios",
                "distrito": "Costera-Canal",
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede mancomunitat",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Sin licencias de obra; trámites administrativos generales",
            },
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": "Costera-Canal",
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios electrónico",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en lacosteracanal.sede.dival.es",
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
