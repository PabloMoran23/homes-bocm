from __future__ import annotations

import hashlib
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

WEB_BASE = "https://www.velezmalaga.es"
SEDE_BASE = "https://sede.velezmalaga.es"
MUNICIPIO = "Vélez-Málaga"
ID_PREFIX = "velez-malaga"

TABLON_LIST_URL = (
    f"{WEB_BASE}/?mod=urbanismo-infraestructuras-operativos&pos=1&tag=tablon-de-anuncios"
)
URBANISMO_HOME = f"{WEB_BASE}/index.php?mod=urbanismo-infraestructuras-operativos"
LICENCIAS_INFO_URL = (
    f"{WEB_BASE}/index.php?mod=urbanismo-infraestructuras-operativos"
    "&tag=solicitudes-de-urbanismo-en-la-sede-electronica"
)
SEDE_CATALOGO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
)

EXTRA_TAG_PAGES: tuple[str, ...] = (
    "modificaciones-de-elementos-tras-la-aprobacion-definitiva-del-expediente-de-adaptacion-a-la-loua",
)

RE_TABLON_DOC = re.compile(
    r'<a class="titulo doc" href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_TABLON_POS = re.compile(
    r"tag=tablon-de-anuncios(?:&amp;|&)pos=(\d+)",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"apertura de (?:actividad|establecimiento)|actuaci[oó]n para)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan |pgou|pgom|convenio|informaci[oó]n p[uú]blica|"
    r"expediente|expte|proyecto|modificaci[oó]n|reparcel|estudio de detalle|"
    r"aprobaci[oó]n|expropiaci[oó]n|urbaniz|sector|gesti[oó]n|divisi[oó]n por fases)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE_SLASH = re.compile(
    r"(?i)(?:exp(?:te)?\.?|exp\.?)\s*[\d./-]*?/(\d{2,4})(?:/|-)",
)
RE_DOC_YEAR = re.compile(r"/documentos/(\d{4})/")
RE_SEDE_TRAMITE = re.compile(
    r'href="([^"]*doEvent\?[^"]*PAGE_CODE=CATALOGO[^"]*)"[^>]*>([^<]{5,200})</a>',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _year_from_expte(text: str) -> int | None:
    m = RE_EXPTE_SLASH.search(text or "")
    if not m:
        return None
    y = m.group(1)
    if len(y) == 4:
        return int(y)
    if len(y) == 2:
        n = int(y)
        return 2000 + n if n < 70 else 1900 + n
    return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    y = _year_from_expte(text)
    if y and 1980 <= y <= 2035:
        return f"{y}-06-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "reparcel" in n:
        return "reparcelación"
    if "urbaniz" in n:
        return "urbanización"
    if "expropiaci" in n:
        return "expropiación"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación PGOU"
    if "pgou" in n or "pgom" in n or "planeam" in n:
        return "planeamiento"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


def _abs_url(href: str) -> str:
    return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href))


class VelezMalagaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Tetraware (tablón urbanismo) + sede STA (403 en CI; catálogo opcional)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_LIST_URL)
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 40))
        self.licencias_info_url = str(self.config.get("licencias_info_url") or LICENCIAS_INFO_URL)
        self.extra_tag_pages = [
            str(u)
            for u in (self.config.get("extra_tag_pages") or EXTRA_TAG_PAGES)
        ]

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-velez-malaga/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _parse_tablon_docs(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, title in RE_TABLON_DOC.findall(html):
            titulo = unescape(re.sub(r"\s+", " ", title)).strip()
            if not titulo:
                continue
            url = _abs_url(href)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_text(titulo),
                    "url": url,
                    "origen": "tablon_urbanismo",
                }
            )
        return rows

    def _tablon_page_url(self, pos: int) -> str:
        if pos <= 1:
            return self.tablon_url
        sep = "&" if "?" in self.tablon_url else "?"
        base = re.sub(r"&pos=\d+", "", self.tablon_url)
        return f"{base}{sep}pos={pos}"

    def _discover_tablon_positions(self, html: str) -> list[int]:
        positions = {1}
        for m in RE_TABLON_POS.finditer(html):
            try:
                positions.add(int(m.group(1)))
            except ValueError:
                continue
        return sorted(positions)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        try:
            first_html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        positions = self._discover_tablon_positions(first_html)
        max_pos = max(positions) if positions else 1
        max_pos = min(max_pos, self.max_tablon_pages)

        for pos in range(1, max_pos + 1):
            try:
                html = first_html if pos == 1 else self._fetch(self._tablon_page_url(pos))
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_docs(html):
                key = row["url"]
                if key not in merged:
                    merged[key] = row
                elif row.get("fecha") and not merged[key].get("fecha"):
                    merged[key]["fecha"] = row["fecha"]

        for tag in self.extra_tag_pages:
            url = f"{self.web_base}/index.php?mod=urbanismo-infraestructuras-operativos&tag={tag}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_docs(html):
                key = row["url"]
                if key not in merged:
                    merged[key] = row

        return list(merged.values())

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(SEDE_CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, label in RE_SEDE_TRAMITE.findall(html):
            titulo = _strip_html(label)
            if not RE_LICENCIA.search(titulo):
                continue
            url = _abs_url(href) if href.startswith("http") else urllib.parse.urljoin(
                f"{self.sede_base}/", href
            )
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "sede_catalogo",
                }
            )
        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.licencias_info_url)
        except urllib.error.URLError:
            html = ""

        info_links = re.findall(
            r'href="(https://sede\.velezmalaga\.es[^"]+|[^"]*CATALOGO[^"]*)"',
            html,
            re.I,
        )
        for href in info_links[:12]:
            url = _abs_url(href) if not href.startswith("http") else href
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Solicitudes de urbanismo — sede electrónica",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "urbanismo_sede_info",
                }
            )
            break

        rows.append(
            {
                "id": _stable_id("lic", self.licencias_info_url),
                "fecha_concesion": None,
                "tipo": "información licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitudes de urbanismo en la sede electrónica (Vélez-Málaga)",
                "url": self.licencias_info_url,
                "source": "ayuntamiento",
                "origen": "urbanismo_web_info",
                "nota": "Sin listado público de licencias concedidas; trámites vía sede STA",
            }
        )
        rows.append(
            {
                "id": _stable_id("lic", SEDE_CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de procedimientos — sede Vélez-Málaga",
                "url": SEDE_CATALOGO_URL,
                "source": "ayuntamiento",
                "origen": "sede_catalogo",
            }
        )

        for item in self._collect_tablon():
            if not RE_LICENCIA.search(item["titulo"]):
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": _proyecto_tipo(item["titulo"]),
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item.get("origen"),
            }
            rows.append(rec)

        for item in self._collect_sede_tramites():
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": None,
                    "tipo": "trámite sede",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": item.get("origen"),
                }
            )

        dedup: dict[str, dict[str, Any]] = {}
        for r in rows:
            dedup[r["id"]] = r
        return list(dedup.values())

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        blob = titulo
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(
            re.sub(r"(?i)licencia", "", blob)
        ):
            return None
        fecha = item.get("fecha") or _fecha_from_text(titulo) or "2020-01-01"
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        if not rows:
            rows.append(
                {
                    "id": _stable_id("proy", URBANISMO_HOME),
                    "municipio": MUNICIPIO,
                    "titulo": "Urbanismo y Arquitectura — Ayuntamiento de Vélez-Málaga",
                    "fecha": "2020-01-01",
                    "tipo": "urbanismo",
                    "url": URBANISMO_HOME,
                    "source": "ayuntamiento",
                    "origen": "urbanismo_home",
                    "nota": "Tablón no accesible; página informativa",
                }
            )
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "info_y_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_info():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_pages_max": self.max_tablon_pages}

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
