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

WEB_BASE = "https://www.olot.cat"
MUNICIPIO = "Olot"
ID_PREFIX = "olot"

PLANEJAMENT_SEEDS: list[tuple[str, str]] = [
    (
        f"{WEB_BASE}/ajuntament/planejament-i-gestio-urbanistica/figures-en-tramit",
        "en_tramit",
    ),
    (
        f"{WEB_BASE}/ajuntament/planejament-i-gestio-urbanistica/figures-aprovades-posterior-2003",
        "aprovades_post_2003",
    ),
    (
        f"{WEB_BASE}/ajuntament/planejament-i-gestio-urbanistica/figures-aprovades-anterior-2003",
        "aprovades_pre_2003",
    ),
]

TRAMITS_URBANISME = (
    f"{WEB_BASE}/tramits/cataleg-de-tramits?filtre_221=S&cat_221=151"
)

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (TRAMITS_URBANISME, "Catàleg tràmits — Urbanisme, Habitatge i Obres"),
    (
        f"{WEB_BASE}/ajuntament/planejament-i-gestio-urbanistica",
        "Planejament i gestió urbanística",
    ),
    ("https://urbanisme.olot.cat", "Assistent tràmits d'urbanisme"),
    (
        "https://tauler.seu.cat/v2/inici?idEns=1711430008",
        "Tauler d'anuncis electrònic (e-TAULER)",
    ),
    ("https://tramits.olot.cat/OAC/SegExpStandalone.jsp?idioma=ca", "Tràmits en línia OAC"),
    ("http://poum.olot.cat", "Revisió POUM (documentació PDF)"),
]

RE_LISTING_PROJECT = re.compile(
    r'<a\s+href="(/ajuntament/planejament-i-gestio-urbanistica/[^"]+/pln\d+/[^"]+)"'
    r'(?:\s+title="([^"]*)")?[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_TRAMIT_LINK = re.compile(
    r'<a\s+href="(/tramits/cataleg-de-tramits/pln221/[^"]+)"'
    r'(?:\s+title="([^"]*)")?[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó] previa|declaraci[oó] responsable|"
    r"obra (?:major|menor)|primera utilitzaci[oó]|urbanitzaci[oó]n|parcel·laci[oó])",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="(/files/doc\d+/[^"]+\.pdf)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, section: str = "") -> str:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [
        int(y.group(1))
        for y in RE_YEAR.finditer(text or "")
        if 1970 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    if section == "en_tramit":
        return f"{datetime.now(timezone.utc).year}-01-01"
    if section == "aprovades_pre_2003":
        return "1998-01-01"
    if section == "aprovades_post_2003":
        return "2010-01-01"
    return "1970-01-01"


def _proyecto_tipo(titulo: str, section: str) -> str:
    n = (titulo or "").lower()
    if "reparcel" in n:
        return "reparcelación"
    if "modificaci" in n and ("poum" in n or "pla general" in n or "pgou" in n):
        return "modificación planeamiento"
    if "pla parcial" in n or re.search(r"\bpp\d+", n):
        return "plan parcial"
    if "pla especial" in n or "pe " in n:
        return "plan especial"
    if "ordenan" in n or "paisatge urb" in n:
        return "ordenanza urbanística"
    if "poum" in n or "pla general" in n or "pgou" in n:
        return "planeamiento general"
    if section == "en_tramit":
        return "planeamiento en trámite"
    return "planeamiento urbanístico"


class OlotAyuntamientoAdapter(AyuntamientoAdapter):
    """Web corporativa iDisc (d2web): figures de planejament + catàleg de tràmits; e-TAULER per edictes."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.planejament_seeds = [
            (str(u), str(s))
            for u, s in (self.config.get("planejament_seeds") or PLANEJAMENT_SEEDS)
        ]
        self.licencia_pages = [
            (str(u), str(t))
            for u, t in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.tramits_urbanisme_url = str(
            self.config.get("tramits_urbanisme_url") or TRAMITS_URBANISME
        )
        self.enrich_details = bool(self.config.get("enrich_details", True))
        self.max_detail_fetches = int(self.config.get("max_detail_fetches", 80))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-olot/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def _parse_listing_projects(self, html: str, section: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title_attr, inner in RE_LISTING_PROJECT.findall(html):
            path = href.split("?")[0].rstrip("/")
            if path in seen:
                continue
            seen.add(path)
            titulo = _strip_html(title_attr or inner)
            if len(titulo) < 4:
                continue
            url = self._abs_url(path)
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo, section),
                    "tipo": _proyecto_tipo(titulo, section),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": f"planejament_{section}",
                    "seccion": section,
                }
            )
        return rows

    def _enrich_project_detail(self, rec: dict[str, Any]) -> dict[str, Any]:
        url = rec.get("url") or ""
        if not url:
            return rec
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rec
        pdfs = RE_PDF_HREF.findall(html)
        blob = " ".join(pdfs)
        fecha = _fecha_from_blob(blob, str(rec.get("seccion") or ""))
        if fecha != "1970-01-01":
            rec["fecha"] = fecha
        if pdfs:
            rec["document_url"] = self._abs_url(pdfs[0])
        og = re.search(r'<meta property="og:description" content="([^"]*)"', html, re.I)
        if og:
            desc = _strip_html(og.group(1))
            if desc and len(desc) > 20:
                rec["resumen"] = desc[:800]
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        detail_budget = self.max_detail_fetches
        for seed_url, section in self.planejament_seeds:
            try:
                html = self._fetch(seed_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for rec in self._parse_listing_projects(html, section):
                if self.enrich_details and detail_budget > 0:
                    rec = self._enrich_project_detail(rec)
                    detail_budget -= 1
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def _collect_tramits_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.tramits_urbanisme_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            html = ""
        for href, title_attr, inner in RE_TRAMIT_LINK.findall(html):
            titulo = _strip_html(title_attr or inner)
            if not RE_LICENCIA.search(titulo):
                continue
            url = self._abs_url(href.split("?")[0])
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _fecha_from_blob(titulo),
                    "tipo": titulo[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "cataleg_tramits",
                }
            )
        for url, label in self.licencia_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": "1970-01-01",
                    "tipo": label[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "info_portal",
                }
            )
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "en_tramit": sum(1 for r in rows if r.get("seccion") == "en_tramit"),
            "post_2003": sum(1 for r in rows if r.get("seccion") == "aprovades_post_2003"),
            "pre_2003": sum(1 for r in rows if r.get("seccion") == "aprovades_pre_2003"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_tramits_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "cataleg": sum(1 for r in rows if r.get("origen") == "cataleg_tramits"),
            "info": sum(1 for r in rows if r.get("origen") == "info_portal"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}
