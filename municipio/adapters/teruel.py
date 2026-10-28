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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.teruel.es"
SEDE_BASE = "https://sede.teruel.es"
MUNICIPIO = "Teruel"
ID_PREFIX = "teruel"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/portal-de-transparencia/instrumentos-de-planeamiento/",
    f"{WEB_BASE}/portal-de-transparencia/modificaciones-del-planeamiento/",
    f"{WEB_BASE}/portal-de-transparencia/plan-general-de-ordenacion-urbana/",
    f"{WEB_BASE}/portal-de-transparencia/convenios-urbanisticos/",
    f"{WEB_BASE}/portal-de-transparencia/autorizaciones-licencias-y-concesiones/",
    "https://pgouteruel.es/mapa-web/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|parcelaci[oó]n|"
    r"inicio de actividad|deber de conservaci[oó]n|edificaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|estudio de detalle|modificaci[oó]n|"
    r"reparcel|peri\b|suznp|suzpt|sector|anuncio.*bop|pol[ií]gono|alineaci|"
    r"instrumento|ordenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(mercadillo|puesto vacante|subvenci[oó]n deportiv|empleo p[uú]blico|"
    r"proceso selectivo|nombramiento|padrones|tribut)",
)
RE_PDF_ANCHOR = re.compile(
    r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOP = re.compile(r"(?i)bop[^0-9]*(\d{1,2})[-/](\d{1,2})[-/](\d{4})|(\d{1,2})[-/](\d{1,2})[-/](\d{4})")


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


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio" in n:
        return "convenio urbanístico"
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "peri" in n:
        return "PERI"
    if "plan parcial" in n or "suznp" in n or "sector" in n:
        return "plan parcial"
    if "anuncio" in n or "bop" in n:
        return "anuncio / publicación"
    return "planeamiento"


def _is_urbanismo_tramite(item: dict[str, Any]) -> bool:
    for kw in item.get("keywordList") or []:
        code = str(kw.get("code") or "")
        desc = str(kw.get("description") or "").lower()
        if code == "TramUrbanismo" or "urbanismo" in desc:
            return True
    name = str(item.get("name") or "").lower()
    return bool(RE_LICENCIA.search(name) or RE_PROYECTO.search(name))


class TeruelAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress transparencia (PDFs) + sede STA (catálogo CATSERV). Tablón STA vía Ajax (no embebido)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-teruel/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _abs_url(self, href: str, page_url: str) -> str:
        return urljoin(page_url, unescape(href))

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_catalog_items(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            if not _is_urbanismo_tramite(item):
                continue
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_transparency_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            if not page_url.startswith(self.web_base):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href, inner in RE_PDF_ANCHOR.findall(html):
                if "favicon" in href.lower() or "file_pdf.png" in href.lower():
                    continue
                pdf_url = self._abs_url(href, page_url)
                if pdf_url in seen:
                    continue
                titulo = _clean_title(inner)
                if not titulo or len(titulo) < 8:
                    titulo = _clean_title(Path(urllib.parse.unquote(pdf_url)).stem.replace("-", " "))
                blob = f"{titulo} {pdf_url}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(pdf_url)
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_text(titulo) or _fecha_from_text(pdf_url),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "transparencia_pdf",
                    }
                )
        return rows

    def _info_licencia_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón anuncios y edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Listado dinámico STA (Ajax); consulta manual en sede",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y urbanismo",
                "url": CATALOGO_URL,
                "source": "ayuntamiento",
                "nota": "Trámites electrónicos (no histórico de concesiones)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{WEB_BASE}/portal-de-transparencia/autorizaciones-licencias-y-concesiones/"),
                "fecha_concesion": None,
                "tipo": "publicaciones transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Autorizaciones, licencias y concesiones (transparencia)",
                "url": f"{WEB_BASE}/portal-de-transparencia/autorizaciones-licencias-y-concesiones/",
                "source": "ayuntamiento",
                "origen": "web_transparencia",
            },
        ]

    def _catalog_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["dboid"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite en sede STA",
            "origen": "catalogo_tramites",
        }

    def _pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]) or RE_EXCLUDE.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["pdf_url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "publicación transparencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia_pdf",
        }

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('pdf_url') or ''}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": "transparencia_pdf",
        }

    def _catalog_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["dboid"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "catalogo_tramites",
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._info_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_items():
            rec = self._catalog_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_transparency_pdfs():
            rec = self._pdf_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._info_licencia_pages():
            existing[rec["id"]] = rec
        for item in self._collect_catalog_items():
            rec = self._catalog_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_transparency_pdfs():
            rec = self._pdf_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for item in self._collect_transparency_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_catalog_items():
            add(self._catalog_to_proyecto(item))
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        def merge(rec: dict[str, Any] | None) -> None:
            if rec:
                existing[rec["id"]] = rec

        for item in self._collect_transparency_pdfs():
            merge(self._pdf_to_proyecto(item))
        for item in self._collect_catalog_items():
            merge(self._catalog_to_proyecto(item))
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
