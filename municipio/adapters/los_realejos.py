from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

WP_BASE = "https://losrealejos.es"
SEDE_BASE = "https://sede.losrealejos.es"
SITCAN_DATASET = "planeamiento-urbanistico-de-los-realejos"
GEOBDP_MUNICIPIO = "38031"
MUNICIPIO = "Los Realejos"
ID_PREFIX = "lre"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo/",
    f"{WP_BASE}/urbanismo/plan-general-de-ordenacion-2/",
    f"{WP_BASE}/urbanismo/plan-general-de-los-realejos-ide-canarias/",
    f"{WP_BASE}/urbanismo/gestion-urbanistica/",
    f"{WP_BASE}/urbanismo/documentos-gerencia/",
    f"{WP_BASE}/urbanismo/tramites-gerencia-urbanismo/",
    f"{WP_BASE}/urbanismo/informacion-general/",
    f"{WP_BASE}/portal-de-transparencia/gerencia-de-urbanismo/",
    f"{WP_BASE}/aprobacion-definitiva-del-plan-general-de-ordenacion-urbana/",
    f"{WP_BASE}/atencion-ciudadana-nuevo-pgo/",
    f"{WP_BASE}/planes-conjuntos-historicos/",
    f"{WP_BASE}/redaccion-planes-realejo-alto-realejo-bajo/",
    f"{WP_BASE}/modificacion-parcial-pgo-nueva-piscina/",
    f"{SEDE_BASE}/castellano/VisorITs/24891A1DA10F4DF6B76E636E84F11358.asp",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"obra (?:mayor|menor)|licencia apertura|actividad (?:inocua|clasificada|minorista)|alineaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|sapur|susno|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|suelo|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|instrumento|urbanizaci[oó]n|pamu|modo parcial|revisi[oó]n parcial)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?losrealejos\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)
RE_BOC_BOP = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_GEOBDP_ZOOM = re.compile(r"App\.Map\.zoomToExtent\((\{.*?\})\);", re.S)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r"<h1[^>]*>([^<]+)",
        r'<meta property="og:title" content="([^"]+)"',
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Los Realejos.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "sapur" in b or "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b or "conjunto hist" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "ordenanza" in b:
        return "ordenanza"
    if "modificaci" in b:
        return "modificación puntual"
    return "urbanismo"


def _utm28n_to_lonlat(x: float, y: float) -> tuple[float, float]:
    k0 = 0.9996
    a = 6378137.0
    e = 0.081819191
    e2 = e * e
    e4 = e2 * e2
    e6 = e4 * e2
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    lon0 = math.radians(-15.0)
    x = x - 500000.0
    m_val = y / k0
    mu = m_val / (a * (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)
    phi1 += (1097 * e1**4 / 512) * math.sin(8 * mu)
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e2 * math.cos(phi1) ** 2 / (1 - e2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d_val = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d_val**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e2) * d_val**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e2 - 3 * c1**2) * d_val**6 / 720
    )
    lon = lon0 + (
        d_val
        - (1 + 2 * t1 + c1) * d_val**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e2 + 24 * t1**2) * d_val**5 / 120
    ) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def _transform_coord_pair(pair: list[float] | tuple[float, float]) -> list[float]:
    lon, lat = _utm28n_to_lonlat(float(pair[0]), float(pair[1]))
    return [lon, lat]


def _transform_coords(node: Any) -> Any:
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            if len(node) == 2 or (len(node) > 2 and not isinstance(node[2], (list, tuple))):
                return _transform_coord_pair(node)
        return [_transform_coords(item) for item in node]
    return node


def _wgs84_geometry(geom: dict[str, Any]) -> dict[str, Any]:
    out = {"type": geom.get("type"), "coordinates": _transform_coords(geom.get("coordinates"))}
    return out


class LosRealejosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (urbanismo/PGO) + sede eMiServicio + SITCAN/GEOBDP planeamiento Canarias."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-realejos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode(encoding, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-realejos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or WP_BASE, href))

    def _discover_wp_posts(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for i in range(1, 8):
            sitemap = f"{WP_BASE}/post-sitemap{i}.xml"
            try:
                xml = self._fetch(sitemap)
            except urllib.error.URLError:
                continue
            for m in RE_SITEMAP_LOC.finditer(xml):
                loc = m.group(1).strip()
                low = loc.lower()
                if any(
                    k in low
                    for k in (
                        "informacion-publica",
                        "plan-general",
                        "pgo",
                        "pgou",
                        "planeam",
                        "urbanismo",
                        "licencia",
                        "convenio",
                        "sapur",
                        "conjuntos-historicos",
                        "modificacion-parcial-pgo",
                    )
                ) and "expediente-sancionador" not in low and "distincion" not in low:
                    if loc not in seen:
                        seen.add(loc)
                        urls.append(loc)
        return urls

    def _geobdp_geometry(self, url: str) -> dict[str, Any] | None:
        if url in self._geom_cache:
            return self._geom_cache[url]
        geom: dict[str, Any] | None = None
        if "geobdp.grafcan.es" not in url:
            self._geom_cache[url] = None
            return None
        try:
            html = self._fetch(url if url.endswith("/") else f"{url}/")
        except urllib.error.URLError:
            self._geom_cache[url] = None
            return None
        m = RE_GEOBDP_ZOOM.search(html)
        if not m:
            self._geom_cache[url] = None
            return None
        try:
            fc = json.loads(m.group(1))
            feats = fc.get("features") or []
            if feats and isinstance(feats[0], dict):
                raw_geom = feats[0].get("geometry")
                if isinstance(raw_geom, dict) and raw_geom.get("coordinates"):
                    crs_name = str((fc.get("crs") or {}).get("properties", {}).get("name", ""))
                    if "32628" in crs_name:
                        geom = _wgs84_geometry(raw_geom)
                    else:
                        geom = raw_geom
        except (json.JSONDecodeError, TypeError, ValueError):
            geom = None
        self._geom_cache[url] = geom
        return geom

    def _attach_geometry(self, rec: dict[str, Any], source_url: str) -> None:
        geobdp_url = rec.get("geobdp_url") or ""
        if not geobdp_url and "geobdp.grafcan.es" in source_url:
            geobdp_url = source_url
        if not geobdp_url:
            return
        geom = self._geobdp_geometry(geobdp_url)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_geobdp_grafcan"
        rec["geometry_source_url"] = geobdp_url
        rec["coord_source"] = "portal_geometry_centroid"

    def _collect_sitcan(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(
                f"https://opendata.sitcan.es/api/3/action/package_show?id={SITCAN_DATASET}"
            )
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        result = data.get("result") or {}
        for res in result.get("resources") or []:
            name = str(res.get("name") or "").strip()
            desc = str(res.get("description") or "")
            fmt = str(res.get("format") or "")
            url = str(res.get("url") or "").strip()
            if not name:
                continue
            blob = f"{name} {desc}"
            if not RE_PROYECTO.search(blob):
                continue
            fecha = _fecha_from_blob(desc) or _fecha_from_blob(name)
            geobdp_url = url if "geobdp.grafcan.es" in url else ""
            if not geobdp_url:
                for candidate in (url, desc):
                    m = re.search(r"https?://geobdp\.grafcan\.es/core/documentos/\d+/?", candidate)
                    if m:
                        geobdp_url = m.group(0)
                        break
            row = {
                "titulo": name[:500],
                "fecha": fecha,
                "url": url or f"https://opendata.sitcan.es/dataset/{SITCAN_DATASET}",
                "blob": blob,
                "origen": "sitcan",
                "formato": fmt,
                "geobdp_url": geobdp_url,
            }
            rows.append(row)
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        page_urls = list(dict.fromkeys([*self.seed_pages, *self._discover_wp_posts()]))
        for page_url in page_urls:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            enc = "iso-8859-1" if "sede.losrealejos.es" in page_url else "utf-8"
            try:
                html = self._fetch(page_url, encoding=enc)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            blob = f"{title} {page_url}"
            fecha = _fecha_from_blob(f"{title} {page_url} {html[:2500]}")
            if RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": page_url,
                        "blob": blob,
                        "origen": "wordpress_page",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {name} {pdf}"
                if not RE_PROYECTO.search(pdf_blob) and not RE_LICENCIA.search(pdf_blob):
                    continue
                rows.append(
                    {
                        "titulo": f"{title}: {name}"[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "wordpress_pdf",
                    }
                )
            for m in RE_WP_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if not re.search(r"(?i)wp-content/uploads.*\.pdf|/descargar/.*\.pdf|transparencia/.*\.pdf", href):
                    continue
                pdf = self._abs_url(href)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {anchor} {name} {pdf}"
                if not RE_PROYECTO.search(pdf_blob) and not RE_LICENCIA.search(pdf_blob):
                    continue
                rows.append(
                    {
                        "titulo": (anchor if len(anchor) > 5 else f"{title}: {name}")[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "wordpress_pdf",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        info_pages = [
            (f"{WP_BASE}/urbanismo/licencias-de-actividades/", "Licencias de actividades — urbanismo"),
            (f"{WP_BASE}/urbanismo/licencias-de-actividades/actividades-clasificadas/", "Actividades clasificadas"),
            (f"{WP_BASE}/urbanismo/licencias-de-actividades/actividades-inocuas/", "Actividades inocuas"),
            (f"{WP_BASE}/urbanismo/licencias-de-actividades/actividades-minoristas/", "Actividades minoristas"),
            (f"{WP_BASE}/urbanismo/tramites-gerencia-urbanismo/", "Trámites Gerencia de Urbanismo"),
            (f"{WP_BASE}/urbanismo/tramites-gerencia-urbanismo/alineaciones-y-rasantes/", "Alineaciones y rasantes"),
            (f"{self.sede_base}/castellano/VisorITs/24891A1DA10F4DF6B76E636E84F11358.asp", "Trámites y gestiones — sede electrónica"),
            (f"{WP_BASE}/tramites-y-gestiones/", "Trámites y gestiones — web municipal"),
        ]
        for url, titulo in info_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "tramite_informativo":
            return row
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("formato"):
            rec["formato"] = row["formato"]
        self._attach_geometry(rec, row.get("geobdp_url") or row.get("url") or "")
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_tramites()
        for row in self._collect_wp_pages():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sede_sitcan"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_sitcan():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_wp_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "wordpress_sitcan_geobdp",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
