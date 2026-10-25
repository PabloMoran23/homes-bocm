from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.lloret.cat"
SEU_BASE = "https://seu.lloret.cat"
TRAMITS_BASE = "https://tramits.lloret.org"
MUNICIPIO = "Lloret de Mar"
ID_PREFIX = "lloret"

DEFAULT_CATEGORIES: list[int] = [7, 8, 34]

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/exposicio-publica",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/exposicio-publica/instruments-de-planejament",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/exposicio-publica/instruments-de-gestio",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/exposicio-publica/projectes-dobra-ordinaria",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/planejament-derivat",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/projecte-4-estacions",
    f"{WEB_BASE}/ca/seccions/planejament-i-gestio-urbanistica/obres-municipals",
]

TRAMITS_INFORMATIVOS: list[tuple[str, str]] = [
    (f"{TRAMITS_BASE}/OAC/CdT.jsp", "Catàleg de tràmits — llicències i urbanisme"),
    (f"{SEU_BASE}/contingutPublic/mostrarContingut/17", "Serveis d'Urbanisme (seu electrònica)"),
    (
        f"{SEU_BASE}/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?lang=ca_ES",
        "Registre de publicacions de planejament i gestió urbanística",
    ),
]

PLONE_RSS = f"{WEB_BASE}/ca/search_rss?SearchableText=planejament"

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]nci|licen|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó]|obra major|demolici[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(planej|urban|pgou|pgom|conveni|exposici[oó] p[uú]blica|"
    r"informaci[oó] p[uú]blica|expedient|modificaci[oó]|ordenaci[oó]|"
    r"gesti[oó] urban|reparcel|estudi|millora urbana|pla parcial|pmu)",
)
RE_PLONE_PATH = re.compile(
    rf'href="((?:https://www\.lloret\.cat)?/ca/seccions/planejament-i-gestio-urbanistica/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_SKIP_TAIL = re.compile(
    r"(?i)(instruments-de-planejament|instruments-de-gestio|projectes-dobra-ordinaria|"
    r"exposicio-publica|planejament-derivat|ubicacio-i-horaris|obres-municipals|"
    r"seguiment-de-les-obres-municipals)$",
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


def _parse_rss_date(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y/%m/%d %H:%M:%S GMT%z"):
        try:
            return datetime.strptime(text.replace(" GMT+2", "+0200").replace(" GMT+1", "+0100"), fmt).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            continue
    return _parse_fecha_dmy(text)


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "millora urbana" in n or re.search(r"\bpmu\b", n):
        return "plan de mejora urbana"
    if "pla parcial" in n or "plan parcial" in n:
        return "plan parcial"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pgou" in n or "pla general" in n:
        return "planeamiento general"
    if "conveni" in n:
        return "convenio urbanístico"
    if "informaci" in n or "exposici" in n or "publicaci" in n:
        return "información pública"
    return "planeamiento / urbanismo"


class LloretDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone lloret.cat + seu.lloret.cat (registre planejament) + catàleg tràmits."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.categories = [int(x) for x in (self.config.get("categories") or DEFAULT_CATEGORIES)]
        self.max_pages = int(self.config.get("max_pages_per_category", 30))
        self.page_size = int(self.config.get("page_size", 10))
        self.seed_pages = list(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lloret-de-mar/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_seu(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.seu_base}{path if path.startswith('/') else '/' + path}"

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{WEB_BASE}/", unescape(href))

    def _parse_registre_page(self, html: str, categoria_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk in html.split('class="data-registre-public'):
            m_link = re.search(r'href="(/registrePublic/registrePublicacio/\d+)"', chunk)
            if not m_link:
                continue
            url = self._abs_seu(m_link.group(1))
            fecha = None
            m_date = re.search(r"<span>(\d{2}/\d{2}/\d{4})", chunk)
            if m_date:
                fecha = _parse_fecha_dmy(m_date.group(1))
            titulo = ""
            m_title = re.search(r'<div class="top">.*?<p>(.*?)</p>', chunk, re.I | re.S)
            if m_title:
                titulo = _strip_html(m_title.group(1))
            if not titulo:
                m_bread = re.search(r"registrePublicacio[^>]*>([^<]{12,})", chunk)
                if m_bread:
                    titulo = _strip_html(m_bread.group(1))
            if not titulo:
                titulo = "Publicació registre urbanístic"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "categoria_id": categoria_id,
                    "origen": "seu_registre_public",
                }
            )
        return rows

    def _collect_seu_registre(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for cat_id in self.categories:
            for page in range(self.max_pages):
                offset = page * self.page_size
                q = urllib.parse.urlencode(
                    {
                        "categoria.id": str(cat_id),
                        "offset": str(offset),
                        "max": str(self.page_size),
                    }
                )
                url = f"{self.seu_base}/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?{q}"
                try:
                    html = self._fetch(url)
                except urllib.error.URLError:
                    break
                batch = self._parse_registre_page(html, cat_id)
                if not batch:
                    break
                for row in batch:
                    by_url[row["url"]] = row
        return list(by_url.values())

    def _collect_plone_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(PLONE_RSS)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        for item in root.findall(".//{http://purl.org/rss/1.0/}item"):
            title = (item.findtext("{http://purl.org/rss/1.0/}title") or "").strip()
            link = (item.findtext("{http://purl.org/rss/1.0/}link") or "").strip()
            if not title or not link:
                continue
            if not RE_PROYECTO.search(title) and "planejament" not in link:
                continue
            date_raw = item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _parse_rss_date(date_raw),
                    "url": link,
                    "origen": "plone_rss",
                }
            )
        return rows

    def _is_plone_project_url(self, url: str) -> bool:
        path = urllib.parse.urlparse(url).path.rstrip("/")
        slug = path.split("/")[-1]
        if RE_SKIP_TAIL.search(slug):
            return False
        if "/exposicio-publica/" in path or "/planejament-derivat/" in path:
            return True
        if "/projecte-" in path:
            return True
        return False

    def _collect_plone_seeds(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_PLONE_PATH.finditer(html):
                link = self._abs_web(m.group(1), seed)
                if not self._is_plone_project_url(link):
                    continue
                path = urllib.parse.urlparse(link).path
                slug = path.rstrip("/").split("/")[-1]
                by_url[link] = {
                    "titulo": slug.replace("-", " ").strip().title()[:500],
                    "url": link,
                    "origen": "plone_exposicion",
                }
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            if h1 and self._is_plone_project_url(seed):
                by_url[seed] = {
                    "titulo": _strip_html(h1.group(1))[:500],
                    "url": seed,
                    "origen": "plone_exposicion",
                }
        return list(by_url.values())

    def _tramits_informativos(self) -> list[dict[str, Any]]:
        return [
            {"titulo": label, "url": url, "fecha": None, "origen": "tramits_informativo"}
            for url, label in TRAMITS_INFORMATIVOS
        ]

    def _proyecto_record(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row.get("titulo") or "Proyecto urbanístico"
        url = row.get("url") or WEB_BASE
        key = f"{url}|{titulo}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha") or "2020-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("categoria_id") is not None:
            rec["categoria_seu"] = row["categoria_id"]
        return rec

    def _licencia_record(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row.get("titulo") or "Licencia / trámite urbanístico"
        url = row.get("url") or TRAMITS_BASE
        key = f"{url}|{titulo}"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": titulo[:300],
            "distrito": "",
            "lat": None,
            "lon": None,
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _merge_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in (
            self._collect_seu_registre()
            + self._collect_plone_rss()
            + self._collect_plone_seeds()
        ):
            rec = self._proyecto_record(row)
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _merge_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in self._tramits_informativos():
            rec = self._licencia_record(row)
            by_id[rec["id"]] = rec
        for row in self._collect_seu_registre():
            if not RE_LICENCIA.search(row.get("titulo") or ""):
                continue
            rec = self._licencia_record(row)
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "seu_registre": sum(1 for r in rows if r.get("origen") == "seu_registre_public"),
            "plone": sum(1 for r in rows if str(r.get("origen", "")).startswith("plone")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
