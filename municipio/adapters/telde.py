from __future__ import annotations

import hashlib
import http.cookiejar
import json
import math
import re
import ssl
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

WEB_BASE = "https://www.telde.es"
SEDE_BASE = "https://telde.sedelectronica.es"
INFORMACION_PUBLICA_URL = f"{WEB_BASE}/areas/urbanismo/informacion-publica/"
URBANISMO_URL = f"{WEB_BASE}/areas/urbanismo/"
TRANSPARENCIA_URB_URL = f"{WEB_BASE}/transparencia/obras-publicas-y-urbanismo/"
MUNICIPIO = "Telde"
ID_PREFIX = "telde"
SITCAN_PACKAGE = "planeamiento-urbanistico-de-telde"
SITCAN_DATASET_URL = f"https://opendata.sitcan.es/dataset/{SITCAN_PACKAGE}"
GEOBDP_MUNICIPIO = "https://geobdp.grafcan.es/core/municipios/35026/"

DEFAULT_SEED_PAGES: list[str] = [
    INFORMACION_PUBLICA_URL,
    URBANISMO_URL,
    TRANSPARENCIA_URB_URL,
    f"{WEB_BASE}/tramites-presenciales/urbanismo/",
]

RE_PREVIEW = re.compile(
    r'href="(https://telde\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://telde\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|"
    r"vehiculos|notificaci[oó]n expediente|igualdad|"
    r"cobranza|iae|ivtm|cementerio|"
    r"calendario fiscal|recaudaci[oó]n|"
    r"fiestas|cine|empleo|deporte|pilates|gimnasia|"
    r"electores|bizum|auto-?taxi|veh[ií]culo|licenciados en derecho)",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|pamu|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto de urbaniz|modificaci[oó]n puntual|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|revisi[oó]n parcial|"
    r"texto refundido|suspensi[oó]n de determinaciones|ordenaci[oó]n)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?telde\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GEOBDP_DOC = re.compile(
    r'href="/core/documentos/(\d+)\.html">([^<]+)',
    re.I,
)
RE_ZOOM_EXTENT = re.compile(
    r"App\.Map\.zoomToExtent\((\{.*?\})\);",
    re.S,
)
RE_GEOBDP_URL = re.compile(r"geobdp\.grafcan\.es/core/documentos/(\d+)")


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
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or " pp " in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "revisi" in b and "parcial" in b:
        return "revisión parcial"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "urbanizaci" in b:
        return "proyecto urbanización"
    if "licencia" in b:
        return "licencia publicada"
    if "ordenanza" in b:
        return "ordenanza"
    if "plano" in b:
        return "planeamiento"
    return "urbanismo"


def _is_valid_canarias(lng: float, lat: float) -> bool:
    return 27.0 <= lat <= 30.0 and -19.0 <= lng <= -12.0


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

    lng_deg = math.degrees(lon)
    lat_deg = math.degrees(lat)
    if not _is_valid_canarias(lng_deg, lat_deg):
        return None
    return lng_deg, lat_deg


def _reproject_coords(node: Any) -> Any:
    if isinstance(node, (list, tuple)):
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
            and not isinstance(node[0], bool)
        ):
            out = _utm28n_to_wgs84(float(node[0]), float(node[1]))
            if out:
                return [out[0], out[1]]
            return [float(node[0]), float(node[1])]
        return [_reproject_coords(x) for x in node]
    return node


def _first_coord_pair(node: Any) -> tuple[float, float] | None:
    if isinstance(node, (list, tuple)):
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
            and not isinstance(node[0], bool)
        ):
            return float(node[0]), float(node[1])
        for item in node:
            pair = _first_coord_pair(item)
            if pair:
                return pair
    return None


def _reproject_geometry(geom: dict[str, Any]) -> dict[str, Any] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return None
    out = {"type": gtype, "coordinates": _reproject_coords(coords)}
    pair = _first_coord_pair(out["coordinates"])
    if not pair or not _is_valid_canarias(pair[0], pair[1]):
        return None
    return out


class TeldeAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress telde.es + sede espublico gestiona (tablón) + SITCAN CKAN + GEOBDP Grafcan."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.sitcan_package = str(self.config.get("sitcan_package") or SITCAN_PACKAGE)
        self.geobdp_municipio = str(self.config.get("geobdp_municipio") or GEOBDP_MUNICIPIO)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._geobdp_doc_index: dict[str, str] | None = None
        self._geometry_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-telde/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.web_base, href))

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
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_axis_order"] = "xy"
        rec["geometry_source"] = "portal_geojson"
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

    def _collect_web_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        for page_url in self.seed_pages:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-1].replace("-", " "))
            blob = f"{title} {page_url}"
            fecha = _fecha_from_blob(f"{title} {page_url} {html[:2000]}")
            if RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": page_url,
                        "blob": blob,
                        "origen": "portal_page",
                        "urls": [page_url],
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
                        "titulo": f"{title}: {name}"[:500] if title else name[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "portal_pdf",
                        "urls": [pdf, page_url],
                    }
                )
        return rows

    def _should_exclude(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob):
            if RE_PROYECTO.search(blob) and (
                "ordenanza" in blob.lower() or "boc" in blob.lower() or "planeam" in blob.lower()
            ):
                return False
            return True
        return False

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0]) if cells else ""
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            expediente = _strip_html(cells[1]) if len(cells) > 1 else ""
            procedimiento = _strip_html(cells[2]) if len(cells) > 2 else ""
            categoria = _strip_html(cells[3]) if len(cells) > 3 else ""
            descripcion = _strip_html(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _strip_html(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "blob": " ".join(
                        (titulo, procedimiento, categoria, descripcion, expediente)
                    ),
                    "origen": origen,
                    "urls": [url],
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "blob": titulo,
                    "origen": origen,
                    "urls": [url],
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info.0", "info_tablon")):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = href if href.startswith("http") else f"{self.sede_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "blob": titulo,
                    "origen": "catalogo_tramites",
                    "urls": [url],
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites telemáticos — licencias de obra y urbanismo",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
            },
            {
                "id": _stable_id("lic", SITCAN_DATASET_URL),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "SITCAN — planeamiento urbanístico sistematizado de Telde",
                "url": SITCAN_DATASET_URL,
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
            },
        ]

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "tramite_informativo":
            return row
        blob = row.get("blob") or row.get("titulo", "")
        if self._should_exclude(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("expediente") or row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo", "")
        if self._should_exclude(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        cat = (row.get("categoria") or "").lower()
        if cat in ("urbanismo", "ordenanzas y reglamentos", "planeamiento general (modificación)"):
            pass
        elif not RE_PROYECTO.search(blob):
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
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        urls = row.get("urls") or [row.get("url", "")]
        self._attach_geometry(rec, row["titulo"], [u for u in urls if u])
        return rec

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
        for row in self._collect_board():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        for row in self._collect_tramites():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        for row in self._collect_web_pages():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "sede_tablon_sitcan_portal",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
        }

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
        raw: list[dict[str, Any]] = []
        for row in self._collect_sitcan():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_board():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_tramites():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_web_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "sitcan_geobdp_sede_portal",
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
