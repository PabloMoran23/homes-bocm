from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.almeriaciudad.es"
MUNICIPIO = "Almería"
ID_PREFIX = "almeria"
COD_INE = "04013"

TABLON_URBANISMO_URL = f"{WEB_BASE}/tablon-de-anuncios?type=All&area=4"
OBRAS_URBANISMO_URL = f"{WEB_BASE}/obras-publicas-y-urbanismo"
TRAMITES_URL = f"{WEB_BASE}/urbanismo/tramites-y-gestiones"
INFO_URBANISMO_URL = f"{WEB_BASE}/urbanismo/informacion-tecnica-de-urbanismo"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio (?:de detalle|de ordenaci[oó]n|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|urbanizaci[oó]n|"
    r"delimitaci[oó]n|avance|ordenaci[oó]n|sector|parcela|suelo)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(sorteo de v\.?p\.?o|registro municipal de demandantes|ordenanza municipal reguladora del "
    r"registro|ordenanza municipal reguladora del paso|bando horario cierre|bando acontecimientos|"
    r"alfaralmer[ií]a|feria de almer[ií]a|subvenci[oó]n|empleo p[uú]blico|proceso selectivo|"
    r"licitaci[oó]n de las parcelas y ambig[uú]s)",
)
RE_TABLON_ITEM = re.compile(
    r'<a href="(/tablon-de-anuncios/[^"]+)">\s*(.*?)\s*</a>\s*</div>\s*'
    r'.*?<time datetime="([^"]+)"',
    re.I | re.S,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PAGER_LAST = re.compile(r'pager__item[^>]*>\s*<a[^>]+href="[^"]*page=(\d+)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_datetime_attr(value: str) -> str | None:
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _fecha_from_blob(text: str) -> str | None:
    for parser in (_parse_fecha_dmy, _fecha_from_datetime_attr):
        d = parser(text)
        if d:
            return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "estudio de ordenaci" in b:
        return "estudio de ordenación"
    if "reparcel" in b:
        return "reparcelación"
    if "urbanizaci" in b:
        return "urbanización"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "delimitaci" in b:
        return "delimitación actuación"
    if "avance" in b:
        return "avance planeamiento"
    return "urbanismo"


class AlmeriaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal almeriaciudad.es (tablón área urbanismo + PGOU PDFs) + WFS Diputación sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 12))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almeria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almeria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, page_url: str = WEB_BASE) -> str:
        return urljoin(page_url, href)

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

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(WFS_SECTORS_URL)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": _norm_text(sector),
                        "geom": geom,
                        "cod_ine": props.get("cod_ine"),
                        "clase_suelo": props.get("clase_suelo"),
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        result: dict[str, Any] | None = None
        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            if len(sector_norm) < 4:
                continue
            if sector_norm in title_norm or re.search(
                rf"\b{re.escape(sector_norm)}\b", title_norm
            ):
                geom = row["geom"]
                sector_escaped = row["sector"].replace("'", "''")
                cql = urllib.parse.quote(
                    f"cod_ine='{COD_INE}' AND sector='{sector_escaped}'"
                )
                query = (
                    "https://app.dipalme.org/geoserver/urbanismo/ows?"
                    "service=WFS&version=2.0.0&request=GetFeature&"
                    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                    f"CQL_FILTER={cql}&"
                    "count=1&outputFormat=application/json&srsName=EPSG:4326"
                )
                result = {
                    "geom_geojson": geom,
                    "geometry_source": "dipalme_wfs_sector",
                    "geometry_source_url": query,
                    "coord_source": "portal_geometry_centroid",
                    "sector_urbanistico": row["sector"],
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    result["lat"], result["lon"] = centroid
                break

        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry_for_title(rec.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _collect_tablon_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        max_page = 0

        try:
            first_html = self._fetch(TABLON_URBANISMO_URL)
        except urllib.error.URLError:
            return rows

        last_match = RE_PAGER_LAST.findall(first_html)
        if last_match:
            max_page = max(int(x) for x in last_match)
        max_page = min(max_page, self.max_tablon_pages)

        for page in range(0, max_page + 1):
            page_url = TABLON_URBANISMO_URL if page == 0 else f"{TABLON_URBANISMO_URL}&page={page}"
            try:
                html = first_html if page == 0 else self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in RE_TABLON_ITEM.finditer(html):
                href, title_html, dt_attr = m.group(1), m.group(2), m.group(3)
                title = _clean_title(title_html)
                url = self._abs_url(href)
                if url in seen_urls or not title:
                    continue
                seen_urls.add(url)

                if RE_TABLON_SKIP.search(title):
                    continue
                if not RE_PROYECTO.search(title):
                    continue

                fecha = _fecha_from_datetime_attr(dt_attr) or _fecha_from_blob(title)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                }
                rows.append(self._enrich_geometry(rec))

        return rows

    def _collect_obras_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(OBRAS_URBANISMO_URL)
        except urllib.error.URLError:
            return rows

        seen: set[str] = set()
        for href in RE_PDF.findall(html):
            pdf_url = self._abs_url(href, OBRAS_URBANISMO_URL)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            filename = pdf_url.rsplit("/", 1)[-1]
            title = _clean_title(filename.replace("_", " ").replace("-", " ").rsplit(".", 1)[0])
            if not RE_PROYECTO.search(title) and not RE_PROYECTO.search(filename):
                continue
            fecha = _fecha_from_blob(filename) or _fecha_from_blob(title)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf_url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{title} {filename}"),
                "url": pdf_url,
                "source": "ayuntamiento",
                "pdf_url": pdf_url,
            }
            rows.append(self._enrich_geometry(rec))
        return rows

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        seeds = [TRAMITES_URL, INFO_URBANISMO_URL]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for seed in seeds:
            if seed in seen:
                continue
            seen.add(seed)
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            title = _clean_title(title_m.group(1)) if title_m else seed.rsplit("/", 1)[-1]
            rec: dict[str, Any] = {
                "id": _stable_id("lic", seed),
                "fecha_concesion": None,
                "tipo": "trámite urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": seed,
                "source": "ayuntamiento",
                "nota": "Página informativa; sede electrónica no accesible desde el scraper",
            }
            rows.append(rec)

            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{8,200})</a>', html, re.I):
                href, link_title = m.group(1), _clean_title(m.group(2))
                if not RE_LICENCIA.search(link_title):
                    continue
                url = self._abs_url(href, seed)
                if url in seen or not url.startswith("http"):
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
                        "titulo": link_title[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Trámite informativo; sin listado público de concesiones",
                    }
                )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_tablon_proyectos():
            add(rec)
        for rec in self._collect_obras_pdfs():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
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
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
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
