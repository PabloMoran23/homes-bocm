from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.albaida.es"
SEDE_BASE = "https://albaida.sede.dival.es"
MUNICIPIO = "Albaida"
ID_PREFIX = "albaida"
INE_MUN = "46024"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URBANISMO = f"{SEDE_BASE}/catalogoservicios.aspx?area=1796&ambito=1"
PGOU_URL = f"{WEB_BASE}/es/content/plan-general-ordenacion-urbana"
URBANISMO_INFO_URL = f"{WEB_BASE}/es/content/informacion"
POLIGONO_URL = f"{WEB_BASE}/es/pagina/poligon-industrial-ferrocarril"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_INVENTARIO = "ms:InventarioSuSuz"
ICV_ZONIFICACION = "ms:Planeamiento.Zonificacion"
GVA_WFS_OFFSETS = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000]

DEFAULT_SEED_PAGES: list[str] = [
    PGOU_URL,
    URBANISMO_INFO_URL,
    POLIGONO_URL,
]

STATIC_PGOU_DOCS: list[dict[str, str]] = [
    {
        "titulo": "PGOU Albaida — Plan General de Ordenación Urbana",
        "url": PGOU_URL,
        "tipo": "PGOU",
        "fecha": "2004-01-01",
    },
    {
        "titulo": "Modificación puntual n.º 5 PGOU Albaida (aprobación definitiva BOP 74/2017)",
        "url": PGOU_URL,
        "tipo": "modificación PGOU",
        "fecha": "2017-04-19",
    },
    {
        "titulo": "Normas urbanísticas PGOU Albaida",
        "url": f"{WEB_BASE}/sites/www.albaida.es/files/files/urbanisme/planols/normurb.pdf",
        "tipo": "normas urbanísticas",
        "fecha": None,
    },
    {
        "titulo": "Polígono industrial Ferrocarril — Albaida",
        "url": POLIGONO_URL,
        "tipo": "plan parcial / polígono industrial",
        "fecha": None,
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|llicències|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|inicio de obra|"
    r"estudi d.integraci[oó]|integraci[oó] paisatg)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"estudi (?:ac[uú]stico|ambiental|d.integraci[oó])|memoria|planos|aprobaci[oó]n|"
    r"edicto|sector|pol[ií]gon|suelo|participaci[oó]|paisatg|reciclatge)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|bolsa de treball|suplement de cr[eé]dit|"
    r"modificaci[oó] pressupost|compte general|ordenan[cç]a.*animal|col[oò]nies felines|"
    r"concurs btt|jurats|bases generals de selecci[oó])",
)
RE_TRAMITE = re.compile(
    r'href="(https://albaida\.sede\.dival\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"'
    r'[^>]*>\s*([^<]+)',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.albaida\.es)?/sites/www\.albaida\.es/files/[^"]+\.(?:pdf|PDF))"',
    re.I,
)
RE_DOC_LINK = re.compile(
    r'href="((?:https://albaida\.sede\.dival\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:S|UE|SD|PP|PRI|PERI)[\s\-]?(?:\d+[a-z]?|[A-Z]+)(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


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


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "modificaci" in n and ("pgou" in n or "plan general" in n):
        return "modificación PGOU"
    if "polígon" in n or "poligon" in n or "industrial" in n:
        return "polígono industrial"
    if "plan parcial" in n or re.search(r"\bs-\d", n):
        return "sector / plan parcial"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "estudi" in n and ("integraci" in n or "paisatg" in n):
        return "estudio integración paisajística"
    if "participaci" in n:
        return "participación ciudadana"
    if "informaci" in n:
        return "información pública"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    return "planeamiento"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _strip_html(m.group(1))
        if len(tok) >= 2:
            tokens.append(tok)
    return tokens


class AlbaidaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede Dival (Sedipualba) + ICV WFS InventarioSuSuz/Zonificacion."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_urbanismo = str(self.config.get("catalogo_urbanismo") or CATALOGO_URBANISMO)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 8))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs = str(geom_cfg.get("wfs_url") or ICV_WFS)
        self.gva_offsets = list(geom_cfg.get("offsets") or GVA_WFS_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        self._inventario_cache: list[dict[str, Any]] | None = None
        self._inventario_by_key: dict[str, dict[str, Any]] | None = None
        self._zonificacion_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 2) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-albaida/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-albaida/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, timeout=45)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].strip(),
                        "%a, %d %b %Y %H:%M:%S",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "blob": title,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _enrich_anuncio_docs(self, row: dict[str, Any]) -> dict[str, Any]:
        url = row.get("url") or ""
        if "anuncio.aspx" not in url:
            return row
        try:
            html = self._fetch(url, timeout=45)
        except urllib.error.URLError:
            return row
        docs = [self._abs_sede(m.group(1)) for m in RE_DOC_LINK.finditer(html)]
        if docs:
            row = dict(row)
            row["pdf_url"] = docs[0]
            row["documentos"] = docs
        fecha = _parse_fecha_dmy(html)
        if fecha:
            row = dict(row)
            row["fecha"] = fecha
        return row

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_urbanismo, timeout=45)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TRAMITE.finditer(html):
            url = m.group(1)
            title = _strip_html(m.group(2))
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica Albaida",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en albaida.sede.dival.es",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_urbanismo),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catàleg de tràmits — Urbanisme",
                "url": self.catalogo_urbanismo,
                "source": "ayuntamiento",
                "nota": "Modelos DR/licencias (URB.001–URB.010) presentables telemáticamente",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_INFO_URL),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Servicio Municipal de Urbanismo — información",
                "url": URBANISMO_INFO_URL,
                "source": "ayuntamiento",
                "nota": "Formularios e información de licencias y declaraciones responsables",
                "origen": "web_tramite",
            },
        ]

    def _wfs_page_url(self, type_name: str, start: int, *, count: int = 200) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": str(count),
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs}?{params}"

    def _collect_inventario_wfs(self) -> list[dict[str, Any]]:
        if self._inventario_cache is not None:
            return self._inventario_cache
        rows: list[dict[str, Any]] = []
        start = 0
        while start < 12000:
            url = self._wfs_page_url(ICV_INVENTARIO, start)
            try:
                raw = self._fetch(url, timeout=90)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != self.cod_ine_mun:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _strip_html(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _strip_html(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _strip_html(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob or None,
                    "url": f"https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz",
                    "tipo": f"sector {clas}" if clas else "sector planeamiento",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                    "wfs_id": fid,
                    "origen": "icv_inventario",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            start += 200
        self._inventario_cache = rows
        self._inventario_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._inventario_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._inventario_by_key[tok.lower()] = rec
        return rows

    def _collect_zonificacion_wfs(self) -> list[dict[str, Any]]:
        if self._zonificacion_cache is not None:
            return self._zonificacion_cache
        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        for start in self.gva_offsets:
            url = self._wfs_page_url(ICV_ZONIFICACION, start, count=500)
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                continue
            for member in root.findall(".//wfs:member", _GML_NS):
                feat_el = member.find("ms:Planeamiento.Zonificacion", _GML_NS)
                if feat_el is None:
                    continue
                props: dict[str, str] = {}
                geom = None
                for child in feat_el:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        pos = child.find(".//gml:posList", _GML_NS)
                        if pos is not None and pos.text:
                            geom = _gml_poslist_to_polygon(pos.text)
                    else:
                        props[tag] = (child.text or "").strip()
                if props.get("cod_ine_mun") != self.cod_ine_mun or not geom:
                    continue
                label = props.get("denominaci") or props.get("expediente") or ""
                exp = props.get("expediente") or ""
                key = f"{exp}:{label}"
                if key in seen:
                    continue
                seen.add(key)
                feats.append(
                    {
                        "label": label,
                        "expediente": exp,
                        "geom": geom,
                        "source_url": url,
                    }
                )
        self._zonificacion_cache = feats
        return feats

    def _match_inventario(self, text: str) -> dict[str, Any] | None:
        if self._inventario_by_key is None:
            self._collect_inventario_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._inventario_by_key or {}).items():
            if len(key) >= 3 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            rec = (self._inventario_by_key or {}).get(tok.lower())
            if rec:
                return rec
        return None

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        title_low = title.lower()

        inv = self._match_inventario(title)
        if inv and inv.get("geom_geojson"):
            return {
                "geom_geojson": inv["geom_geojson"],
                "geometry_source": inv.get("geometry_source", "portal_wfs"),
                "geometry_source_url": inv.get("geometry_source_url"),
                "coord_source": "portal_geometry_centroid",
            }

        if any(k in title_low for k in ("plan general", "pgou", "normas urban", "zonific")):
            feats = self._collect_zonificacion_wfs()
            if feats:
                geoms = [f["geom"] for f in feats if f.get("geom")]
                geom = _merge_geometries(geoms)
                if geom:
                    return {
                        "geom_geojson": geom,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": feats[0].get("source_url") or self.icv_wfs,
                        "coord_source": "portal_geometry_centroid",
                    }
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("url") or blob
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _collect_web_pgou(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        queue = list(self.seed_pages)
        visited: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            page = queue.pop(0).rstrip("/")
            if page in visited:
                continue
            visited.add(page)
            try:
                html = self._fetch(page, timeout=20, retries=1)
            except urllib.error.URLError:
                continue
            for href in RE_PDF_HREF.findall(html):
                full = self._abs_web(href)
                if full in seen_urls:
                    continue
                seen_urls.add(full)
                name = urllib.parse.unquote(full.split("/")[-1])
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", full),
                    "municipio": MUNICIPIO,
                    "titulo": f"PGOU Albaida — {name}",
                    "fecha": None,
                    "tipo": _proyecto_tipo(name),
                    "url": full,
                    "source": "ayuntamiento",
                    "origen": "drupal_pdf",
                }
                self._enrich_geometry(rec)
                rows.append(rec)

        for doc in STATIC_PGOU_DOCS:
            url = doc["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            rec = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": doc["titulo"],
                "fecha": doc.get("fecha"),
                "tipo": doc.get("tipo") or "planeamiento",
                "url": url,
                "source": "ayuntamiento",
                "origen": "drupal_seed",
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_inventario_wfs():
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv-inv:{item.get('wfs_id')}:{item.get('titulo')}"),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": item.get("fecha"),
                "tipo": item.get("tipo") or "sector planeamiento",
                "url": item.get("url") or self.icv_wfs,
                "source": "ayuntamiento",
                "origen": "icv_inventario",
            }
            if item.get("geom_geojson"):
                rec["geom_geojson"] = item["geom_geojson"]
                rec["geometry_source"] = item.get("geometry_source")
                rec["geometry_source_url"] = item.get("geometry_source_url")
                rec["coord_source"] = item.get("coord_source")
                if item.get("lat") is not None:
                    rec["lat"] = item["lat"]
                    rec["lon"] = item["lon"]
            rows.append(rec)

        feats = self._collect_zonificacion_wfs()
        labels: set[str] = set()
        for feat in feats:
            label = (feat.get("label") or "").strip()
            if not label or label in labels:
                continue
            labels.add(label)
            exp = feat.get("expediente") or ""
            titulo = f"{label} (exp. {exp})" if exp else label
            geoms = [f["geom"] for f in feats if (f.get("label") or "").strip() == label and f.get("geom")]
            geom = _merge_geometries(geoms)
            rec = {
                "id": _stable_id("proy", f"icv-zon:{exp}:{label}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(label),
                "url": feat.get("source_url") or self.icv_wfs,
                "source": "ayuntamiento",
                "origen": "icv_zonificacion",
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = feat.get("source_url")
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_tramites_urbanismo():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for rec in self._collect_tramites_urbanismo():
            existing[rec["id"]] = rec
        for item in self._collect_tablon_rss():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
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

        for item in self._collect_tablon_rss():
            enriched = self._enrich_anuncio_docs(item)
            add(self._tablon_to_proyecto(enriched))

        for rec in self._collect_web_pgou():
            add(rec)

        for rec in self._collect_icv_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
            "icv": sum(1 for r in rows if str(r.get("origen", "")).startswith("icv")),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
