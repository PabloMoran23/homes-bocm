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

WEB_BASE = "https://www.granollers.cat"
SEDE_PORTAL = "https://seuelectronica.granollers.cat/portal/sede"
SEDE_STA = "https://seuelectronica.granollers.cat"
MUNICIPIO = "Granollers"
ID_PREFIX = "granollers"

DEFAULT_PLAN_PAGES: list[dict[str, str]] = [
    {
        "url": (
            f"{SEDE_PORTAL}/se_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=144"
            "&language=ca&codResi=1&codMenuPN=21&codMenuSN=133&codMenu=134"
        ),
        "seccion": "planejament_en_tramit",
    },
    {
        "url": (
            f"{SEDE_PORTAL}/se_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=145"
            "&language=ca&codResi=1&codMenuPN=21&codMenuSN=133&codMenu=135"
        ),
        "seccion": "planejament_derivat_aprovat",
    },
    {
        "url": (
            f"{SEDE_PORTAL}/se_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=151"
            "&language=ca&codResi=1&codMenuPN=21&codMenuSN=133&codMenu=207"
        ),
        "seccion": "instruments_gestio",
    },
    {
        "url": (
            f"{SEDE_PORTAL}/se_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=102"
            "&language=ca&codResi=1&codMenuPN=20&codMenuSN=75&codMenu=73"
        ),
        "seccion": "instruments_planificacio",
    },
]

TRAMIT_SEARCH_TERMS: tuple[str, ...] = (
    "llicència d'obres",
    "llicencia d'obres",
    "comunicació prèvia",
    "comunicacion previa",
    "declaració responsable",
    "obra major",
    "obra menor",
    "primera ocupació",
)

RE_PROJECT_BLOCK = re.compile(r"<strong>([^<]+)</strong>(.*?)(?=<strong>|\Z)", re.I | re.S)
RE_PDF_LINK = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_TRAMIT_LINK = re.compile(r'href="(se_contenedor2\.jsp[^"]+)"[^>]*>([^<]{5,})</a>', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|primera ocupaci[oó]n|"
    r"projecte t[eè]cnic|certificat t[eè]cnic)",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _fecha_from_text(text: str) -> str:
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return "1970-01-01"


def _proyecto_tipo(titulo: str, seccion: str = "") -> str:
    blob = f"{titulo} {seccion}".lower()
    if "pla de millora urbana" in blob or "pmu" in blob:
        return "plan de mejora urbana"
    if "pla director" in blob:
        return "plan director"
    if "pla local" in blob and "habitatge" in blob:
        return "plan local de vivienda"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "gesti" in blob:
        return "gestión urbanística"
    if "tramit" in blob or "exposici" in blob or "informaci" in blob:
        return "información pública"
    return "planeamiento"


class GranollersAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal (urbanisme) + sede JSP (planejament PDFs) + catálogo trámites STA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_portal = str(self.config.get("sede_portal") or SEDE_PORTAL).rstrip("/")
        self.sede_sta = str(self.config.get("sede_sta") or SEDE_STA).rstrip("/")
        self.plan_pages = list(self.config.get("plan_pages") or DEFAULT_PLAN_PAGES)
        self.tramit_terms = tuple(self.config.get("tramit_search_terms") or TRAMIT_SEARCH_TERMS)

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-granollers/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        if charset.lower() in {"iso-8859-1", "latin-1", "windows-1252"}:
            return raw.decode("latin-1", errors="replace")
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")

    def _abs_sede(self, href: str, page_url: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_portal}/", href)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            out.append(obj)
                    except json.JSONDecodeError:
                        pass
        return out

    def _parse_planeamiento_page(self, html: str, page_url: str, seccion: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PROJECT_BLOCK.finditer(html):
            titulo = _clean_title(m.group(1))
            if len(titulo) < 8:
                continue
            if not re.search(
                r"(?i)(pla|plan|sector|urban|pmu|instrument|gesti|modific|parcial|especial|millora|director)",
                titulo,
            ):
                continue
            block = m.group(2)
            pdfs = [self._abs_sede(h, page_url) for h in RE_PDF_LINK.findall(block)]
            pdfs = list(dict.fromkeys(pdfs))
            if not pdfs and "archivosrel" not in block.lower():
                continue
            key = f"{seccion}:{titulo}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_text(titulo),
                "tipo": _proyecto_tipo(titulo, seccion),
                "url": page_url,
                "source": "ayuntamiento",
                "origen": f"sede_{seccion}",
            }
            if pdfs:
                rec["documento_url"] = pdfs[0]
                rec["documentos"] = pdfs[:12]
            rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for entry in self.plan_pages:
            page_url = str(entry["url"])
            seccion = str(entry.get("seccion") or "planejament")
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for rec in self._parse_planeamiento_page(html, page_url, seccion):
                by_key[rec["titulo"].lower()] = rec
        return list(by_key.values())

    def _tramit_catalog_url(self, keyword: str) -> str:
        q = urllib.parse.urlencode(
            {
                "seccion": "s_ltra_d12_v1.jsp",
                "codbusqueda": "65",
                "language": "ca",
                "codResi": "1",
                "codMenuPN": "21",
                "codMenu": "48",
                "buscadorPalabrasClave": keyword,
                "layout": "se_contenedor1.jsp",
            }
        )
        return f"{self.sede_portal}/se_contenedor1.jsp?{q}"

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []
        for term in self.tramit_terms:
            try:
                html = self._fetch(self._tramit_catalog_url(term))
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in RE_TRAMIT_LINK.finditer(html):
                href, titulo = m.group(1), _clean_title(m.group(2))
                if not RE_LICENCIA.search(titulo):
                    continue
                if re.search(r"(?i)(autotaxi|taxi|subministrament d'aigua|menjador escolar)", titulo):
                    continue
                url = self._abs_sede(href, self._tramit_catalog_url(term))
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": _fecha_from_text(titulo),
                        "tipo": titulo[:200],
                        "distrito": "",
                        "lat": None,
                        "lon": None,
                        "source": "ayuntamiento",
                        "titulo": titulo,
                        "url": url,
                        "origen": "catalogo_tramites_sede",
                    }
                )
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_planejament"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_tramites_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "catalogo_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
