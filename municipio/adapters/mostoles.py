from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.mostoles.es"
GMU_DOCS = (
    f"{BASE}/es/ayuntamiento/concejalias/concejalia-urbanismo-vivienda-patrimonio-mantenimiento-ciud/"
    "gerencia-municipal-urbanismo-gmu/documentos-interes"
)
TABLON_HISTORICO = (
    f"{BASE}/SEDE_ELECTRONICA/es/tablon-anuncios/historico-tablon-anuncios-ayuntamiento-mostoles"
)
TABLON_ACTUAL = f"{BASE}/SEDE_ELECTRONICA/es/tablon-anuncios"
TABLON_PLANES = f"{BASE}/SEDE_ELECTRONICA/es/tablon-anuncios/planes-urbanisticos"

DEFAULT_GMU_PDF_PAGES: list[tuple[str, str]] = [
    (f"{GMU_DOCS}/convenios-urbanisticos", "convenio urbanístico"),
    (f"{GMU_DOCS}/edictos-gerencia-municipal-urbanismo", "edicto GMU"),
    (f"{GMU_DOCS}/estudios-incidencia-ambiental", "estudio incidencia ambiental"),
    (f"{GMU_DOCS}/estudios-acusticos", "estudio acústico"),
]

DEFAULT_TABLON_PAGES = (
    TABLON_ACTUAL,
    TABLON_HISTORICO,
    TABLON_PLANES,
)

TABLON_SEARCH_TERMS = (
    "urbanismo",
    "Gerencia Municipal de Urbanismo",
    "plenario",
    "plan parcial",
    "plan especial",
    "convenio",
    "Expte:",
    "informacion publica",
    "reparcelacion",
    "PGUO",
    "estudio de detalle",
    "edicto",
    "solicitud",
)

RE_TABLON_LIST = re.compile(
    r'class="contentName"><a href="(/SEDE_ELECTRONICA/es/tablon-anuncios/[^"]+)"'
    r'[^>]*class="cmContentLink">([^<]+)',
    re.I,
)
RE_TABLON_LIST_ALT = re.compile(
    r'<a href="(/SEDE_ELECTRONICA/es/tablon-anuncios/[^"]+)"[^>]*class="cmContentLink"[^>]*>'
    r"(?:<span class=\"content-name\">)?([^<]+)",
    re.I,
)
RE_CONTENT_TITLE = re.compile(
    r'<h2[^>]*id="contentName"[^>]*class="contentMainTitle"[^>]*>([^<]+)',
    re.I,
)
RE_DATE = re.compile(r"^(\d{2}/\d{2}/\d{4})")
RE_EXPTE = re.compile(r"Expte:\s*([A-Z0-9./\s]+?)(?:\s*\||$|\.|\s{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|instada|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(acuerdo plenario|informaci[oó]n p[uú]blica|plan (?:parcial|especial|especial)|"
    r"pguo|convenio|expediente|U\d{3}/|PLAN/|reparcelaci|estudio de detalle|"
    r"gerencia municipal de urbanismo|aprobaci[oó]n definitiva|orden de ejecuci|"
    r"edicto|incidencia ambiental|estudio ac[uú]stico|mejora urbana|segregaci)",
)


def _norm_ascii(s: str) -> str:
    t = unicodedata.normalize("NFD", s or "")
    return t.encode("ascii", "ignore").decode("ascii").lower()


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"mostoles-{prefix}-{h}"


def _parse_date_ddmmyyyy(s: str) -> str | None:
    m = RE_DATE.match(s.strip())
    if not m:
        return None
    try:
        d = datetime.strptime(m.group(1), "%d/%m/%Y")
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    if not m:
        m = re.search(r"(?i)Exp\.?\s*([A-Z]?\d+)", text)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _iso_from_year(text: str) -> str | None:
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text) if 1980 <= int(m.group(1)) <= 2030]
    if not years:
        return None
    return f"{max(years)}-01-01"


class MostolesAyuntamientoAdapter(AyuntamientoAdapter):
    """Tablón sede + GMU documentos (convenios, edictos, EIA) + planes urbanísticos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.search_terms = list(self.config.get("search_terms") or TABLON_SEARCH_TERMS)
        self.seed_urls = list(self.config.get("seed_urls") or [])
        raw_pages = self.config.get("tablon_pages") or list(DEFAULT_TABLON_PAGES)
        self.tablon_pages = [str(p) for p in raw_pages]
        raw_gmu = self.config.get("gmu_pdf_pages")
        if raw_gmu:
            self.gmu_pdf_pages = [(p["url"], p.get("tipo", "documento GMU")) for p in raw_gmu]
        else:
            self.gmu_pdf_pages = list(DEFAULT_GMU_PDF_PAGES)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mostoles/1.0")},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return urllib.parse.urljoin(BASE, path)

    def _extract_tablon_items(self, html: str) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for pat in (RE_TABLON_LIST, RE_TABLON_LIST_ALT):
            for m in pat.finditer(html):
                title = unescape(m.group(2).strip())
                url = self._abs_url(m.group(1))
                if title and "/tablon-anuncios/" in url:
                    items.append((title, url))
        return items

    def _search_tablon(self, term: str) -> list[tuple[str, str]]:
        params = {
            "formName": "searchForm",
            "name": term,
            "searchType": "0",
            "sortIndex": "181",
            "search": "Buscar",
        }
        url = f"{TABLON_HISTORICO}.buscar?{urllib.parse.urlencode(params)}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        return self._extract_tablon_items(html)

    def _fetch_detail(self, url: str) -> tuple[str, list[str]]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return "", []
        m = RE_CONTENT_TITLE.search(html)
        title = unescape(m.group(1).strip()) if m else ""
        pdfs = [self._abs_url(x) for x in re.findall(r'href="([^"]+\.ficheros/[^"]+\.pdf)"', html, re.I)]
        return title, pdfs

    def _collect_tablon(self) -> dict[str, tuple[str, str, list[str]]]:
        """url -> (title, url, pdfs)."""
        by_url: dict[str, tuple[str, str, list[str]]] = {}

        def add(title: str, url: str, pdfs: list[str] | None = None) -> None:
            u = self._abs_url(url)
            prev = by_url.get(u)
            pdfs = pdfs or (prev[2] if prev else [])
            t = title or (prev[0] if prev else "")
            by_url[u] = (t, u, pdfs)

        for url in self.seed_urls:
            title, pdfs = self._fetch_detail(url)
            add(title, url, pdfs)

        for page in self.tablon_pages:
            try:
                html = self._fetch(page)
                for title, path in self._extract_tablon_items(html):
                    add(title, path)
            except urllib.error.URLError:
                continue

        for term in self.search_terms:
            for title, path in self._search_tablon(term):
                add(title, path)

        enrich_keys = ("licencia", "urbanismo", "plan-especial", "plan-parcial", "informacion-publica", "plenario")
        for u, (title, url, pdfs) in list(by_url.items()):
            if title and pdfs:
                continue
            slug = _norm_ascii(u)
            if not title and any(k in slug for k in enrich_keys):
                t, p = self._fetch_detail(url)
                by_url[u] = (t or title, url, p or pdfs)

        return by_url

    def _fetch_gmu_pdfs(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for page_url, tipo in self.gmu_pdf_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in re.finditer(r'href="([^"]+\.ficheros/[^"]+\.pdf)"', html, re.I):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                out.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": "Móstoles",
                        "titulo": name[:500],
                        "fecha": _iso_from_year(name) or "1970-01-01",
                        "tipo": tipo,
                        "url": pdf,
                        "source": "ayuntamiento",
                        "expte": _parse_expte(name),
                        "origen": page_url,
                    }
                )
        return out

    def _title_to_licencia(self, title: str, url: str, pdfs: list[str]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        fecha = _parse_date_ddmmyyyy(title) or _iso_from_year(title)
        expte = _parse_expte(title)
        tipo_m = re.search(r"(?i)para (?:la |el )?([^.,]+)", title)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", expte or url),
            "fecha_concesion": fecha,
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte,
            "url": url,
            "source": "ayuntamiento",
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _title_to_proyecto(self, title: str, url: str, pdfs: list[str]) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        fecha = _parse_date_ddmmyyyy(title) or _iso_from_year(title)
        expte = _parse_expte(title)
        tipo = "urbanismo"
        if re.search(r"(?i)acuerdo plenario", title):
            tipo = "acuerdo plenario"
        elif re.search(r"(?i)plan especial|plan parcial|mejora urbana|segregaci", title):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", title):
            tipo = "información pública"
        elif re.search(r"(?i)convenio", title):
            tipo = "convenio"
        elif re.search(r"(?i)incidencia ambiental", title):
            tipo = "estudio ambiental"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", expte or url),
            "municipio": "Móstoles",
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
            "expte": expte,
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon()
        rows: list[dict[str, Any]] = []
        for title, url, pdfs in tablon.values():
            if not title:
                continue
            rec = self._title_to_licencia(title, url, pdfs)
            if rec:
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_sources": len(self.tablon_pages)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        tablon = self._collect_tablon()
        added = 0
        for title, url, pdfs in tablon.values():
            if not title:
                continue
            rec = self._title_to_licencia(title, url, pdfs)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "count": len(rows),
            "added": added,
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for title, url, pdfs in tablon.values():
            if not title:
                continue
            rec = self._title_to_proyecto(title, url, pdfs)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._fetch_gmu_pdfs():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
            "gmu_pages": len(self.gmu_pdf_pages),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        tablon = self._collect_tablon()
        for title, url, pdfs in tablon.values():
            if not title:
                continue
            rec = self._title_to_proyecto(title, url, pdfs)
            if rec:
                existing[rec["id"]] = rec
        for rec in self._fetch_gmu_pdfs():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "count": len(rows),
            "added": max(0, added),
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}
