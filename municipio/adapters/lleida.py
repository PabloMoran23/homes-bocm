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

URBANISME_WEB = "https://urbanisme.paeria.cat"
SEU_BASE = "https://seu.paeria.cat"
TRAMITS_BASE = "https://tramits.paeria.cat"
MUNICIPIO = "Lleida"
ID_PREFIX = "lleida"

URBANISME_RSS = f"{URBANISME_WEB}/rss.xml"

DEFAULT_CATEGORIES: list[int] = [7, 154, 8, 328, 337]

DEFAULT_SEED_PAGES: list[str] = [
    f"{URBANISME_WEB}/planejament-i-habitatge/registre-de-planejament-urbanistic-de-lleida",
    f"{URBANISME_WEB}/planejament-i-habitatge/exposicio-publica-resolucions-amb-incidencia-ambiental",
    f"{URBANISME_WEB}/planejament-i-habitatge/convenis-urbanistics-pdf",
    f"{URBANISME_WEB}/planejament-i-habitatge/poum-lleida-2025",
    f"{URBANISME_WEB}/informacio-general/tauler-danuncis-e-tauler",
]

TRAMITS_LICENCIA: list[tuple[str, str]] = [
    (
        f"{TRAMITS_BASE}/Ciutadania/DetallTramit.aspx?IdTramit=1811",
        "Llicències urbanístiques",
    ),
    (
        f"{TRAMITS_BASE}/Ciutadania/DetallTramit.aspx?IdTramit=3320",
        "Comunicació prèvia / declaració responsable d'obres",
    ),
    (
        f"{TRAMITS_BASE}/Ciutadania/DetallTramit.aspx?IdTramit=3317",
        "Llicència d'obres",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]nci|licen|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó]|obra major|demolici[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(planej|urban|poum|pgou|pgom|conveni|exposici[oó] p[uú]blica|"
    r"informaci[oó] p[uú]blica|expedient|modificaci[oó] puntual|aprovaci[oó]|"
    r"ordenaci[oó]|gesti[oó] urban|reparcel|estudi|patrimoni|catalog)",
)
RE_PLONE_LINK = re.compile(
    rf'href="((?:https://urbanisme\.paeria\.cat)?/[^"#?]+\.(?:pdf|html)?[^"]*)"',
    re.I,
)
RE_PLONE_PATH = re.compile(
    r'href="(https://urbanisme\.paeria\.cat/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            dt = datetime.strptime(text.replace(" CEST", "+0200").replace(" CET", "+0100"), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return _parse_fecha_dmy(text)


class LleidaAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu electrònica (registre planejament) + web Plone urbanisme + tràmits informatius."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or URBANISME_WEB)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.categories = [int(x) for x in (self.config.get("categories") or DEFAULT_CATEGORIES)]
        self.max_pages = int(self.config.get("max_pages_per_category", 25))
        self.page_size = int(self.config.get("page_size", 10))
        self.seed_pages = list(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lleida/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_seu(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.seu_base}{path if path.startswith('/') else '/' + path}"

    def _parse_registre_page(self, html: str, categoria_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk in html.split('class="data-registre-public')[1:]:
            m_date = re.search(r"<span>(\d{2}/\d{2}/\d{4})", chunk)
            m_link = re.search(r'href="(/registrePublic/registrePublicacio/\d+)"', chunk)
            if not m_link:
                continue
            url = self._abs_seu(m_link.group(1))
            fecha = _parse_fecha_dmy(m_date.group(1) if m_date else "")
            expediente = ""
            m_exp = re.search(r"expedient:</span>\s*([^<]+)", chunk, re.I)
            if m_exp:
                expediente = _strip_html(m_exp.group(1))
            instrument = ""
            m_ins = re.search(r"Instrument:</span>\s*([^<]+)", chunk, re.I)
            if m_ins:
                instrument = _strip_html(m_ins.group(1))
            tema = ""
            m_tema = re.search(r"Tema:</span>\s*([^<]+)", chunk, re.I)
            if m_tema:
                tema = _strip_html(m_tema.group(1))
            titulo = tema or expediente or instrument or "Publicació registre urbanístic"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "expediente": expediente,
                    "instrument": instrument,
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
                    {"categoria.id": str(cat_id), "offset": str(offset), "max": str(self.page_size)}
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
                if f"offset={offset + self.page_size}" not in html and page > 0:
                    break
        return list(by_url.values())

    def _collect_plone_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(URBANISME_RSS)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or item.findtext("guid") or "").strip()
            if not title or not link:
                continue
            if not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _parse_rss_date(item.findtext("pubDate") or ""),
                    "url": link,
                    "origen": "urbanisme_rss",
                }
            )
        return rows

    def _collect_plone_seeds(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_PLONE_PATH.finditer(html):
                link = m.group(1)
                path = urllib.parse.urlparse(link).path
                if not RE_PROYECTO.search(path) and not RE_PROYECTO.search(link):
                    continue
                if "/noticies/" in path and "planejament" not in path:
                    continue
                by_url[link] = {
                    "titulo": _slug_to_title(path.rstrip("/").split("/")[-1]),
                    "url": link,
                    "origen": "urbanisme_plone",
                }
        return list(by_url.values())

    def _tramits_informativos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, label in TRAMITS_LICENCIA:
            rows.append(
                {
                    "titulo": label,
                    "url": url,
                    "fecha": None,
                    "origen": "tramits_informativo",
                }
            )
        return rows

    def _proyecto_record(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row.get("titulo") or "Proyecto urbanístico"
        url = row.get("url") or URBANISME_WEB
        key = f"{url}|{titulo}"
        tipo = row.get("instrument") or "planeamiento / urbanismo"
        if row.get("expediente"):
            tipo = f"{tipo} — {row['expediente'][:120]}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": tipo[:300],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expediente"] = row["expediente"]
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
            "rss": sum(1 for r in rows if r.get("origen") == "urbanisme_rss"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)


def _slug_to_title(slug: str) -> str:
    t = slug.replace("-", " ").strip()
    return t[:1].upper() + t[1:] if t else slug
