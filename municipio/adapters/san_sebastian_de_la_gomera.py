from __future__ import annotations

import hashlib
import json
import math
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
from municipio.geometry import geometry_centroid

WP_BASE = "https://sansebastiangomera.org"
SEDE_BASE = "https://eadmin.sansebastiangomera.org"
MUNICIPIO = "San Sebastián de La Gomera"
ID_PREFIX = "ssg"
SITCAN_PACKAGE = "planeamiento-urbanistico-de-san-sebastian-de-la-gomera"
GEOBDP_MUNICIPIO = "https://geobdp.grafcan.es/core/municipios/38036/"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/obras-y-servicios/",
    f"{SEDE_BASE}/publico/tablon",
    f"{SEDE_BASE}/publico/edictos",
    f"{SEDE_BASE}/publico/procedimientos",
    f"{SEDE_BASE}/publico/territorio/informeurbanistico",
    f"{SEDE_BASE}/publico/territorio/cexp",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n.*(?:pgo|pgou|plan)|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|normas urban|ordenanza.*urban|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|sapu|peri)",
)
RE_NOISE = re.compile(
    r"(?i)(modificaci[oó]n de cr[eé]dito|modificaci[oó]n presupuestaria|lista cobratoria|"
    r"proceso selectivo|tribunal calificador|proces\.sel\.ordenanza|plaza de ordenanza|"
    r"impuesto de actividades|iae 20\d\d|padr[oó]n de habitantes|presupuesto general|"
    r"plan econ[oó]mico-financiero|lista de reserva|estabilizaci[oó]n empleo|"
    r"ocupaci[oó]n de suelo p[uú]blico.*fiestas|gesti[oó]n de calidad.*norma internacional)",
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?sansebastiangomera\.org)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>", re.I)
RE_GEOBDP_DOC = re.compile(
    r'href="/core/documentos/(\d+)\.html">([^<]+)',
    re.I,
)
RE_ZOOM_EXTENT = re.compile(
    r"App\.Map\.zoomToExtent\((\{.*?\})\);",
    re.S,
)
RE_GEOBDP_URL = re.compile(r"geobdp\.grafcan\.es/core/documentos/(\d+)")
RE_TABLON_EDICTO = re.compile(
    r'/publico/edictos/(\d+)"[^>]*>.*?>([^<]{10,300})<',
    re.I | re.S,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_title(text: str) -> str:
    t = unescape(text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


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
            t = re.sub(r"\s*[-|–].*(?:Gomera|Ayuntamiento|Sede).*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or "sapu" in b:
        return "plan parcial"
    if "plan especial" in b or " peri " in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "normas urban" in b or "ordenanza" in b:
        return "normas urbanísticas"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _utm28n_to_wgs84(easting: float, northing: float) -> tuple[float, float] | None:
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e = math.sqrt(2 * f - f * f)
    e2 = e * e / (1 - e * e)
    zone = 28
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    x = easting - 500000.0
    y = northing
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))

    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)

    n1 = a / math.sqrt(1 - e**2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e2 * math.cos(phi1) ** 2
    r1 = a * (1 - e**2) / (1 - e**2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e2) * d**4 / 24
    )
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


def _reproject_geometry(geom: dict[str, Any]) -> dict[str, Any]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return geom

    def _walk(node: Any) -> Any:
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
                pair = _utm28n_to_wgs84(float(node[0]), float(node[1]))
                if pair:
                    return [pair[1], pair[0]]
                return list(node)
            return [_walk(item) for item in node]
        return node

    return {"type": gtype, "coordinates": _walk(coords)}


class SanSebastianDeLaGomeraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede Galileo GIYS + SITCAN CKAN + GEOBDP Grafcan (Canarias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sitcan_package = str(self.config.get("sitcan_package") or SITCAN_PACKAGE)
        self.geobdp_municipio = str(self.config.get("geobdp_municipio") or GEOBDP_MUNICIPIO)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.edictos_rss = str(
            self.config.get("edictos_rss") or f"{self.sede_base}/publico/sindicacion/edictos/RSS"
        )
        self._geobdp_doc_index: dict[str, str] | None = None
        self._geometry_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-san-sebastian-de-la-gomera/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.wp_base, href))

    def _load_geobdp_index(self) -> dict[str, str]:
        if self._geobdp_doc_index is not None:
            return self._geobdp_doc_index
        index: dict[str, str] = {}
        try:
            html = self._fetch(self.geobdp_municipio)
        except urllib.error.URLError:
            self._geobdp_doc_index = index
            return index
        for m in RE_GEOBDP_DOC.finditer(html):
            doc_id, title = m.group(1), _strip_html(m.group(2))
            index[_norm_title(title)] = doc_id
            short = _norm_title(re.sub(r"\(.*\)$", "", title))
            if short:
                index.setdefault(short, doc_id)
        self._geobdp_doc_index = index
        return index

    def _match_geobdp_doc(self, title: str, urls: list[str]) -> str | None:
        for url in urls:
            m = RE_GEOBDP_URL.search(url or "")
            if m:
                return m.group(1)
        norm = _norm_title(title)
        idx = self._load_geobdp_index()
        if norm in idx:
            return idx[norm]
        for key, doc_id in idx.items():
            if len(key) > 20 and (key in norm or norm in key):
                return doc_id
        return None

    def _fetch_geobdp_geometry(self, doc_id: str) -> dict[str, Any] | None:
        if doc_id in self._geometry_cache:
            return self._geometry_cache[doc_id]
        url = f"https://geobdp.grafcan.es/core/documentos/{doc_id}.html"
        geom_out: dict[str, Any] | None = None
        try:
            html = self._fetch(url)
            m = RE_ZOOM_EXTENT.search(html)
            if m:
                fc = json.loads(m.group(1))
                features = fc.get("features") or []
                if features:
                    raw_geom = features[0].get("geometry")
                    if isinstance(raw_geom, dict):
                        geom_out = _reproject_geometry(raw_geom)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            geom_out = None
        self._geometry_cache[doc_id] = geom_out
        return geom_out

    def _attach_geometry(self, rec: dict[str, Any], title: str, urls: list[str]) -> None:
        doc_id = self._match_geobdp_doc(title, urls)
        if not doc_id:
            return
        geom = self._fetch_geobdp_geometry(doc_id)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_geobdp_grafcan"
        rec["geometry_source_url"] = f"https://geobdp.grafcan.es/core/documentos/{doc_id}.html"
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_sitcan(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        api = (
            "https://opendata.sitcan.es/api/3/action/package_show"
            f"?id={urllib.parse.quote(self.sitcan_package)}"
        )
        try:
            payload = self._fetch_json(api)
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        resources = (payload.get("result") or {}).get("resources") or []
        seen: set[str] = set()
        grouped: dict[str, dict[str, Any]] = {}
        for res in resources:
            name = (res.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            url = (res.get("url") or "").strip()
            grouped[name] = {
                "titulo": name[:500],
                "fecha": _fecha_from_blob(name),
                "url": url or f"https://opendata.sitcan.es/dataset/{self.sitcan_package}",
                "blob": name,
                "origen": "sitcan_ckan",
                "urls": [url] if url else [],
            }
        for res in resources:
            name = (res.get("name") or "").strip()
            if name not in grouped:
                continue
            url = (res.get("url") or "").strip()
            if url and url not in grouped[name]["urls"]:
                grouped[name]["urls"].append(url)
            if url and "geobdp" in url:
                grouped[name]["url"] = url
        return list(grouped.values())

    def _collect_edictos_rss(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml = self._fetch(self.edictos_rss)
        except urllib.error.URLError:
            return rows
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            date_el = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            url = (link_el.text or "").strip()
            desc = _strip_html(desc_el.text if desc_el is not None else "")
            blob = f"{title} {desc}"
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].replace("Z", "+0000"),
                        "%a, %d %b %Y %H:%M:%S %z",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = _fecha_from_blob(date_el.text)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": blob,
                    "origen": "sede_edictos_rss",
                    "urls": [url],
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(f"{self.sede_base}/publico/tablon")
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in re.finditer(r'/publico/edictos/(\d+)', html):
            eid = m.group(1)
            if eid in seen:
                continue
            seen.add(eid)
            start = max(0, m.start() - 800)
            chunk = html[start : m.end() + 200]
            title = ""
            for pat in (
                r'descripcionLinkButton[^>]*>([^<]+)',
                r'>(Anuncio:[^<]{10,250})<',
                r'>([^<]{20,250}(?:urban|planeam|licen|normas|ordenanza|expediente)[^<]{0,80})<',
            ):
                tm = re.search(pat, chunk, re.I)
                if tm:
                    title = _strip_html(tm.group(1))
                    if len(title) > 10:
                        break
            if not title:
                title = f"Edicto {eid}"
            url = f"{self.sede_base}/publico/edictos/{eid}"
            blob = title
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(chunk),
                    "url": url,
                    "blob": blob,
                    "origen": "sede_tablon",
                    "urls": [url],
                }
            )
        return rows

    def _discover_wp_posts(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for i in range(1, 5):
            sitemap = f"{self.wp_base}/post-sitemap{i}.xml"
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
                        "reparcel",
                        "urbanistic",
                    )
                ) and "plan-de-emergencia" not in low and "plan-de-empleo" not in low:
                    if loc not in seen:
                        seen.add(loc)
                        urls.append(loc)
        return urls

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        page_urls = list(dict.fromkeys([*self.seed_pages, *self._discover_wp_posts()]))
        for page_url in page_urls:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
            blob = f"{title} {page_url}"
            fecha = _fecha_from_blob(f"{title} {page_url} {html[:2000]}")
            if RE_NOISE.search(blob):
                continue
            if RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": page_url,
                        "blob": blob,
                        "origen": "wordpress_page",
                        "urls": [page_url],
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {name} {pdf}"
                if RE_NOISE.search(pdf_blob):
                    continue
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
                        "urls": [pdf, page_url],
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        info_pages = [
            (f"{self.sede_base}/publico/procedimientos", "Catálogo procedimientos — URBANISMO"),
            (f"{self.sede_base}/publico/territorio/informeurbanistico", "Informe urbanístico — sede"),
            (f"{self.sede_base}/publico/tablon", "Tablón de edictos y anuncios"),
            (f"{self.sede_base}/publico/edictos", "Edictos publicados"),
            (f"{self.wp_base}/obras-y-servicios/", "Obras y Servicios — área municipal"),
        ]
        rows: list[dict[str, Any]] = []
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
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada" if row.get("origen") == "sede_edictos_rss" else "licencia / trámite",
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
        if RE_NOISE.search(blob):
            return None
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
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        urls = row.get("urls") or [row.get("url", "")]
        self._attach_geometry(rec, row["titulo"], [u for u in urls if u])
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
        for row in self._collect_edictos_rss():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        for row in self._collect_tablon():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
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
        for row in self._collect_edictos_rss():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_tablon():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_wp_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sede_sitcan_geobdp"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
