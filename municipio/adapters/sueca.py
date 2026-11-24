from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

import hashlib
import http.client
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

WEB_BASE = "https://www.sueca.es"
SEDE_BASE = "https://carpetaciutadana.sueca.es"
OPENSIAC_PREFIX = "/opensiac6"
INFO_PUBLICA_URL = f"{SEDE_BASE}{OPENSIAC_PREFIX}/informacionpublica/infopublica.action?edictos=1"
TRAMITES_CATALOGO = f"{SEDE_BASE}{OPENSIAC_PREFIX}/informacionpublica/tramites_enter.action"
MUNICIPIO = "Sueca"
ID_PREFIX = "sueca"
INE_MUNICIPIO = "46230"

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "ms:InventarioSuSuz"
ICV_TYPE_ZON = "Planeamiento.Zonificacion"
ICV_OFFSETS = [8000, 10000, 12000]
VISOR_GVA_ZON = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/val/seccion/urbanisme",
    f"{WEB_BASE}/val/urbanisme",
    f"{WEB_BASE}/val/listado-titulares/aviso",
    f"{WEB_BASE}/val/transparencia/pla-general",
    f"{WEB_BASE}/val/transparencia/informacio-urbanistica",
    f"{WEB_BASE}/val/transparencia/ambits-eatim",
    f"{WEB_BASE}/val/pagina-transparencia/documents-informacio-publica",
    f"{WEB_BASE}/val/tramites",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó] responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|inicio de obra|"
    r"instancia.?obres|compatibilidad urban|ambiental funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"expropi|nareng|sector|ue[\s\-]?\d|unidad de actuaci[oó]n|"
    r"estudi (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|"
    r"aprobaci[oó]n (?:inicial|definitiva)|conveni|urbanitz)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"calendario fiscal|calendari fiscal|subvenci[oó]n|precios p[uú]blicos|"
    r"ordenanza fiscal|convocatoria.*pleno|juez de paz|campanya.*mosquits|"
    r"control de vectors)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_INDEX_ROW = re.compile(
    r"listaPublicacionesDescripcion\">(.*?)</td>\s*<td[^>]*>\s*(\d{2}/\d{2}/\d{4}).*?"
    r"infopublica_ver\.action[^?]*\?id=(\d+)",
    re.S | re.I,
)
RE_LISTING_ROW = re.compile(
    r'infopublica_ver\.action[^"]*id=(\d+)"[^>]*title="(?:Mostrar|Amosar) ([^"]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.sueca\.es)?/sites/www\.sueca\.es/files/[^"]+\.(?:pdf|PDF|zip))"',
    re.I,
)
RE_AVISO_HREF = re.compile(
    r'href="((?:https://www\.sueca\.es)?/(?:val|es)/(?:pagina-aviso|aviso)/[^"#?]+)"',
    re.I,
)
RE_AVISO_LIST = re.compile(
    r'href="(/val/pagina-aviso/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector|ue|ua)\s*([A-Z]?\s*\d+|[A-Z])\b",
)

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return None  # No observed full date; preserve unknown precision.
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nareng" in b or "plan especial" in b:
        return "plan especial"
    if "pla general" in b or "pgou" in b:
        return "plan general"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "expropi" in b:
        return "expropiación"
    if "sector" in b:
        return "sector planeamiento"
    if re.search(r"\bue[\s\-]?\d+", b):
        return "unidad de ejecución"
    return "planeamiento"


def _gml_poslist_to_geojson(poslist: str) -> dict[str, Any] | None:
    coords: list[list[float]] = []
    parts = (poslist or "").split()
    if len(parts) < 6:
        return None
    for i in range(0, len(parts) - 1, 2):
        try:
            lat = float(parts[i])
            lon = float(parts[i + 1])
        except ValueError:
            continue
        coords.append([lon, lat])
    if len(coords) < 4:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry") if isinstance(f, dict) and "geometry" in f else f.get("geom_geojson")
        if not isinstance(g, dict):
            continue
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


def _parse_gml_feature(member: ET.Element) -> dict[str, Any] | None:
    feat = member[0]
    props: dict[str, str | None] = {}
    geom: dict[str, Any] | None = None
    for child in feat:
        tag = child.tag.split("}")[-1]
        if tag == "msGeometry":
            polygon = child.find(".//gml:Polygon", GML_NS)
            if polygon is not None:
                pos = polygon.find(".//gml:posList", GML_NS)
                if pos is not None and pos.text:
                    geom = _gml_poslist_to_geojson(pos.text)
            continue
        if tag == "boundedBy":
            continue
        props[tag] = (child.text or "").strip() or None
    if props.get("cod_ine_mun") != INE_MUNICIPIO:
        return None
    return {"props": props, "geom": geom}


class SuecaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede OpenSIAC6 + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.opensiac_prefix = str(self.config.get("opensiac_prefix") or OPENSIAC_PREFIX)
        self.info_publica_url = str(self.config.get("info_publica_url") or INFO_PUBLICA_URL)
        self.tramites_catalogo_url = str(self.config.get("tramites_catalogo_url") or TRAMITES_CATALOGO)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.icv_type_zon = str(geom_cfg.get("type_name_zon") or ICV_TYPE_ZON)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.ine_municipio = str(geom_cfg.get("ine_municipio") or INE_MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._icv_zones_cache: list[dict[str, Any]] | None = None
        import http.cookiejar
        import ssl

        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _request_with_retry(self, url: str, timeout: int = 60) -> bytes:
        ua = self.config.get("user_agent", "poc-bocm-sueca/1.0")
        last_err: Exception | None = None
        for attempt in range(4):
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, ConnectionResetError, http.client.IncompleteRead) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch(self, url: str, *, timeout: int = 25) -> str:
        return self._request_with_retry(url, timeout=timeout).decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        return self._request_with_retry(url, timeout=timeout)

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        raw = self._fetch_bytes(url, timeout=timeout)
        return json.loads(raw.decode("utf-8", errors="replace"))

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        max_pages = int(self.config.get("wfs_max_pages") or 35)
        page_size = int(self.config.get("wfs_page_size") or 100)
        empty_pages = 0
        for page in range(max_pages):
            start = page * page_size
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.wfs_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": str(page_size),
                    "startIndex": str(start),
                }
            )
            url = f"{self.wfs_base}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError, http.client.IncompleteRead):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                break
            matched = 0
            for member in members:
                parsed = _parse_gml_feature(member)
                if parsed:
                    rows.append(parsed)
                    matched += 1
            if matched == 0:
                empty_pages += 1
                if empty_pages >= 4:
                    break
            else:
                empty_pages = 0
            if len(rows) >= int(self.config.get("wfs_max_features") or 300):
                break

        self._wfs_cache = rows
        return rows

    def _wfs_query_url(self, ambito_id: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "1",
                "CQL_FILTER": f"id='{_sql_escape(ambito_id)}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._load_wfs_ambitos():
            props = item["props"]
            geom = item.get("geom")
            pp = props.get("pp") or ""
            ue = props.get("ue") or ""
            clas = props.get("clasificacion") or ""
            titulo = f"{clas} {pp}".strip()
            if ue and ue not in titulo:
                titulo = f"{titulo} — {ue}".strip(" —")
            fecha = props.get("f_aprob") or props.get("f_public")
            key = f"wfs:{props.get('id')}:{pp}:{ue}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{pp} {ue} {clas}"),
                "url": (
                    "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                    f"#municipio={MUNICIPIO}"
                ),
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "sector": pp,
                "ue": ue,
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = self._wfs_query_url(str(props.get("id") or key))
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _collect_icv_zonificacion_proyectos(self) -> list[dict[str, Any]]:
        if self._icv_zones_cache is not None:
            zones = self._icv_zones_cache
        else:
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for start in self.icv_offsets:
                params = urllib.parse.urlencode(
                    {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeName": self.icv_type_zon,
                        "outputFormat": "application/json; subtype=geojson",
                        "srsName": "EPSG:4326",
                        "count": "500",
                        "startIndex": str(start),
                    }
                )
                url = f"{self.wfs_base}?{params}"
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError, http.client.IncompleteRead):
                    continue
                batch = data.get("features") or []
                if not batch:
                    break
                for feat in batch:
                    if not isinstance(feat, dict):
                        continue
                    props = feat.get("properties") or {}
                    if str(props.get("cod_ine_mun") or "") != self.ine_municipio:
                        continue
                    den = str(props.get("denominaci") or "").strip()
                    exp = str(props.get("expediente") or "").strip()
                    if not den:
                        continue
                    grouped.setdefault((den, exp), []).append(feat)

            zones = []
            for (den, exp), feats in grouped.items():
                merged = _merge_geometries(feats)
                zones.append(
                    {
                        "denominaci": den,
                        "expediente": exp,
                        "geom_geojson": merged,
                        "geometry_source_url": (
                            f"{self.wfs_base}?service=WFS&request=GetFeature&"
                            f"typeName={self.icv_type_zon}&cod_ine_mun={self.ine_municipio}"
                        ),
                    }
                )
            self._icv_zones_cache = zones

        rows: list[dict[str, Any]] = []
        for zone in zones:
            titulo = zone["denominaci"]
            geom = zone.get("geom_geojson")
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv-zon:{zone.get('expediente')}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(titulo),
                "url": VISOR_GVA_ZON,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = zone.get("geometry_source_url")
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            page_title = _strip_html(h1_m.group(1)) if h1_m else page_url

            if RE_PROYECTO.search(page_title) or RE_LICENCIA.search(page_title):
                if page_url not in seen:
                    seen.add(page_url)
                    rows.append(
                        {
                            "titulo": page_title[:500],
                            "fecha": _fecha_from_blob(page_title),
                            "url": page_url,
                            "page_url": page_url,
                            "blob": f"{page_title} {page_url}",
                            "origen": "drupal_pagina",
                        }
                    )

            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                doc_url = self._abs_web(href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                name = unescape(urllib.parse.unquote(Path(href).name))
                titulo = f"{page_title} — {name}"
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name),
                        "url": doc_url,
                        "page_url": page_url,
                        "blob": f"{titulo} {page_url}",
                        "origen": "drupal_pdf",
                    }
                )

            for m in RE_AVISO_HREF.finditer(html):
                path = m.group(1)
                aviso_url = self._abs_web(path)
                if aviso_url in seen:
                    continue
                slug_part = path.rsplit("/", 1)[-1]
                titulo = slug_part.replace("-", " ")
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                seen.add(aviso_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(slug_part),
                        "url": aviso_url,
                        "page_url": page_url,
                        "blob": f"{titulo} {aviso_url}",
                        "origen": "drupal_aviso",
                    }
                )
        return rows

    def _opensiac_ver_url(self, pub_id: str) -> str:
        return (
            f"{self.sede_base}{self.opensiac_prefix}/informacionpublica/"
            f"infopublica_ver.action?id={pub_id}"
        )

    def _parse_infopublica_index(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_INDEX_ROW.finditer(html):
            pub_id = m.group(3)
            if pub_id in seen:
                continue
            seen.add(pub_id)
            titulo = _strip_html(m.group(1))[:500]
            fecha = _parse_fecha_dmy(m.group(2))
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo,
                    "fecha": fecha,
                    "url": self._opensiac_ver_url(pub_id),
                    "blob": titulo,
                    "origen": "tablon_opensiac",
                }
            )
        for m in RE_LISTING_ROW.finditer(html):
            pub_id = m.group(1)
            if pub_id in seen:
                continue
            seen.add(pub_id)
            titulo = _strip_html(m.group(2))[:500]
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo,
                    "fecha": None,
                    "url": self._opensiac_ver_url(pub_id),
                    "blob": titulo,
                    "origen": "tablon_opensiac",
                }
            )
        return rows

    def _collect_opensiac(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for url in (
            self.info_publica_url,
            f"{self.sede_base}{self.opensiac_prefix}/informacionpublica/infopublica.action",
        ):
            try:
                html = self._fetch(url, timeout=90)
            except urllib.error.URLError:
                continue
            for row in self._parse_infopublica_index(html):
                merged[row["pub_id"]] = row
        return list(merged.values())

    def _collect_aviso_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(f"{self.web_base}/val/listado-titulares/aviso")
        except urllib.error.URLError:
            return rows
        paths = sorted(set(RE_AVISO_LIST.findall(html)))
        for path in paths[:12]:
            aviso_url = self._abs_web(path)
            try:
                page = self._fetch(aviso_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.I | re.S)
            titulo = _strip_html(h1_m.group(1)) if h1_m else path.rsplit("/", 1)[-1].replace("-", " ")
            blob = f"{titulo} {aviso_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            fecha = _parse_fecha_dmy(page) or _fecha_from_blob(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": aviso_url,
                    "blob": blob[:1200],
                    "origen": "drupal_aviso",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.info_publica_url),
                "fecha_concesion": None,
                "tipo": "tablón edictos OpenSIAC",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Información pública — sede electrónica Sueca",
                "url": self.info_publica_url,
                "source": "ayuntamiento",
                "nota": "Publicaciones en carpetaciutadana.sueca.es (OpenSIAC6)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.tramites_catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — seu electrònica",
                "url": self.tramites_catalogo_url,
                "source": "ayuntamiento",
                "nota": "Licencias de obra y actividad vía OpenSIAC (sin histórico detallado)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/val/tramites"),
                "fecha_concesion": None,
                "tipo": "trámites web municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tràmits i serveis — urbanisme",
                "url": f"{self.web_base}/val/tramites",
                "source": "ayuntamiento",
                "nota": "Formularios e información pública en web Drupal",
                "origen": "web_tramite",
            },
        ]

    def _match_geometry(self, titulo: str) -> dict[str, Any] | None:
        blob = titulo.upper()
        for item in self._load_wfs_ambitos():
            props = item["props"]
            pp = str(props.get("pp") or "").upper()
            ue = str(props.get("ue") or "").upper()
            if pp and pp in blob:
                return item
            if ue and re.search(rf"\b{re.escape(ue)}\b", blob):
                return item
        m = RE_SECTOR_CODE.search(titulo)
        if m:
            code = re.sub(r"\s+", " ", m.group(1).strip()).upper()
            for item in self._load_wfs_ambitos():
                props = item["props"]
                pp = str(props.get("pp") or "").upper()
                if code in pp or pp.endswith(code):
                    return item
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        match = self._match_geometry(rec.get("titulo") or "")
        if not match:
            return
        geom = match.get("geom")
        if not geom:
            return
        props = match["props"]
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = self._wfs_query_url(str(props.get("id") or ""))
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            if not re.search(
                r"(?i)(pgou|planeam|urban|licencia|llic|obra|sector|suelo|informaci[oó]n p[uú]blica|agenda urbana|pla general|eatim)",
                blob,
            ):
                return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _opensiac_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pub_id") or row["url"]
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_opensiac",
        }
        self._attach_geometry(rec)
        return rec

    def _opensiac_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pub_id") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_opensiac",
        }
        self._attach_geometry(rec)
        return rec

    def _aviso_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "drupal_aviso",
        }
        self._attach_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "drupal_pagina",
        }
        self._attach_geometry(rec)
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        for item in self._collect_opensiac():
            rec = self._opensiac_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_opensiac"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_opensiac():
            rec = self._opensiac_to_licencia(item)
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

        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))
        for item in self._collect_aviso_pages():
            add(self._aviso_to_proyecto(item))
        for item in self._collect_opensiac():
            add(self._opensiac_to_proyecto(item))
        if self.config.get("wfs_zon_enabled"):
            try:
                for rec in self._collect_icv_zonificacion_proyectos():
                    add(rec)
            except (urllib.error.URLError, http.client.IncompleteRead, json.JSONDecodeError):
                pass

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if str(r.get("origen") or "").startswith("drupal")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_opensiac"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
