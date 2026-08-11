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
from municipio.geometry import geometry_centroid

BASE = "https://www.santamartadetormes.es"
SEDE_BASE = "https://santamartadetormes.sedelectronica.es"
MUNICIPIO = "Santa Marta de Tormes"
ID_PREFIX = "santa-marta-de-tormes"
SIUCYL_WFS = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"

URBANISMO_URL = f"{BASE}/urbanismo"
PGOU_URL = f"{BASE}/plan-general-de-ordenacion-urbana-pgou"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    PGOU_URL,
    f"{BASE}/inspeccion-tecnica-de-edificios",
    f"{BASE}/requerimientos-tecnicos",
    f"{BASE}/exposicion-publica-sector-uz-7",
    f"{BASE}/acuerdo-de-aprobacion-definitiva-del-plan-parcial-del-sector-de-suelo-urbanizable-uz-7-del-pgou",
    f"{BASE}/aprobacion-definitiva-del-estudio-de-detalle-del-sector-unc-6",
    f"{BASE}/estudio-de-detalle-unc-1a-rotonda-del-tormes-norte-a-del-pgou",
    f"{BASE}/estudio-detalle-y-proyecto-de-actuacion-del-sector-unc-1-a",
    f"{BASE}/mofidicaciones-puntual-sector-unc-a3",
    f"{BASE}/modificacion-puntual-en-la-manzana-con-ref-catastral-96660",
    f"{BASE}/modificacion-sobre-los-usos-posibles-en-las-parcelas-de-servicios-comunitarios",
    f"{BASE}/modificacion-puntual-del-pgou-referida-a-los-articulos-84-85-y-193-de-la-normativa-urbanistica",
    f"{BASE}/aprobacion-inicial-a-la-modificaciones-puntuales-al-pgou",
    f"{BASE}/aprobacion-inicial-del-plan-especial-en-terreno-rustico",
]

LICENCIA_INFO_PAGES: list[tuple[str, str]] = [
    (
        "Licencia urbanística / obra (sede electrónica)",
        f"{SEDE_BASE}/",
    ),
    (
        "Inspección Técnica de Edificios (ITE)",
        f"{BASE}/inspeccion-tecnica-de-edificios",
    ),
    (
        "Requerimientos técnicos de urbanismo",
        f"{BASE}/requerimientos-tecnicos",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|ite\b|inspecci[oó]n t[eé]cnica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|aprobaci[oó]n|reparcel|sector|estudio de detalle|"
    r"actuaci[oó]n urban|urbanizaci[oó]n|ordenanza)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})')
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.santamartadetormes\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_INTERNAL_LINK = re.compile(
    r'href="(https://www\.santamartadetormes\.es/[^"#?]+)"',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"UZ[-\s]?\d+|"
    r"UNC[-\s]?(?:A\d+|\d+(?:[-\s]?[A])?)"
    r")\b",
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


def _parse_fecha_iso(html: str) -> str | None:
    m = RE_FECHA_ISO.search(html or "")
    return m.group(1) if m else None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "", code)
    code = re.sub(r"^UZ(\d+)$", r"UZ-\1", code)
    code = re.sub(r"^UNC(\d+)$", r"UNC-\1", code)
    m = re.match(r"^UNC-(\d+)([A])$", code)
    if m:
        return f"UNC-{m.group(1)}-{m.group(2)}"
    m = re.match(r"^UNC(\d+)-([A])$", code)
    if m:
        return f"UNC-{m.group(1)}-{m.group(2)}"
    return code


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(title: str, url: str) -> str:
    blob = f"{title} {url}".lower()
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "plan parcial" in blob or "estudio de detalle" in blob:
        return "planeamiento"
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual PGOU"
    if "pgou" in blob or "planeam" in blob or "ordenaci" in blob:
        return "planeamiento"
    if "plan especial" in blob:
        return "plan especial"
    return "urbanismo"


class SantaMartaDeTormesAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal (CMS propio) + geometría parcial vía SIUCyL WFS sectores PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 60))
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("base_url") or SIUCYL_WFS).rstrip("/")
        self.wfs_layer = str(geom_cfg.get("layer") or "urbanismo:plau_cyl_sectores")
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or MUNICIPIO)
        self._sector_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santa-marta-de-tormes/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{BASE}{href if href.startswith('/') else '/' + href}"

    def _page_title(self, html: str, fallback: str) -> str:
        m = RE_H1.search(html)
        if m:
            return _strip_html(m.group(1)) or fallback
        return fallback

    def _wfs_sector_geometry(self, sector_code: str) -> tuple[dict[str, Any] | None, str | None]:
        if sector_code in self._sector_cache:
            hit = self._sector_cache[sector_code]
            if hit:
                return hit["geom_geojson"], hit["geometry_source_url"]
            return None, None

        safe_code = sector_code.replace("'", "''")
        mun = self.wfs_municipio.replace("'", "''")
        cql = f"n_mun='{mun}' AND n_num_sect='{safe_code}'"
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_layer,
                "count": "1",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_base}?{qs}"
        geom: dict[str, Any] | None = None
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santa-marta-de-tormes/1.0")},
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            feats = data.get("features") or []
            if feats and isinstance(feats[0], dict):
                geom = feats[0].get("geometry")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            geom = None

        if isinstance(geom, dict) and geom.get("type"):
            self._sector_cache[sector_code] = {"geom_geojson": geom, "geometry_source_url": url}
            return geom, url
        self._sector_cache[sector_code] = None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "url", "slug"))
        for code in _sector_codes_from_text(blob):
            geom, source_url = self._wfs_sector_geometry(code)
            if not geom:
                continue
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = source_url
            rec["coord_source"] = "portal_geometry_centroid"
            rec["sector_code"] = code
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            return

    def _page_to_proyecto(self, url: str, html: str) -> dict[str, Any] | None:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        title = self._page_title(html, slug.replace("-", " "))
        blob = f"{title} {url}"
        if not RE_PROYECTO.search(blob):
            return None
        fecha = _parse_fecha_iso(html) or _parse_fecha_dmy(html)
        pdfs = [self._abs_url(m.group(1)) for m in RE_PDF_HREF.finditer(html)]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(title, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": "portal_web",
            "slug": slug,
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
            if len(pdfs) > 1:
                rec["pdf_urls"] = pdfs[:30]
        self._attach_geometry(rec)
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            rec = self._page_to_proyecto(url, html)
            if rec and rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                rows.append(rec)

            if len(visited) < self.max_crawl_pages:
                for m in RE_INTERNAL_LINK.finditer(html):
                    link = m.group(1).rstrip("/")
                    if link in visited or link in queue:
                        continue
                    low = link.lower()
                    if any(
                        x in low
                        for x in (
                            "noticias",
                            "cultura",
                            "museos",
                            "autobuses",
                            "cookies",
                            "privacidad",
                            "contacto",
                            "ayuda",
                            "buzon",
                            "carrera",
                            "grabacion",
                            "formacion",
                            "medio-ambiente",
                            "corporacion",
                            "telefonos",
                            "documentacion-necesaria",
                            "protocolo",
                            "ordenanzas",
                        )
                    ):
                        continue
                    if any(
                        x in low
                        for x in (
                            "urbanismo",
                            "pgou",
                            "sector",
                            "modificacion",
                            "aprobacion",
                            "estudio",
                            "exposicion",
                            "plan-",
                            "unc",
                            "uz-",
                        )
                    ):
                        queue.append(link)

        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for title, url in LICENCIA_INFO_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; sin listado público de licencias concedidas",
                    "origen": "portal_web",
                }
            )
        return rows

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "origen": "portal_web"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "origen": "portal_web",
        }

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
