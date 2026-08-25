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

WEB_BASE = "https://www.alberic.es"
SEDE_BASE = "https://alberic.sede.dival.es"
TRANSPARENCY_BASE = "https://transparencia.alberic.es"
API_BASE = "https://api.digitalvalue.es/alberic/collections"
MUNICIPIO = "Alberic"
ID_PREFIX = "alberic"
INE_COD_MUN = "46005"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
URBANISMO_URL = f"{WEB_BASE}/es/pagina/urbanismo"
TRANSPARENCY_URBANISMO_URL = f"{TRANSPARENCY_BASE}/es/transparencia/planejament-urbanistic"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "Planeamiento.Zonificacion"
GVA_WFS_OFFSETS = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000]

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/seccion/urbanismo",
    URBANISMO_URL,
    f"{WEB_BASE}/es/pagina/plan-general-ordenacion-urbana",
    f"{WEB_BASE}/es/pagina/planeamiento-general-12",
    f"{WEB_BASE}/es/pagina/gestion-urbanistica",
    f"{WEB_BASE}/es/pagina/tramitaciones-licencias-declaraciones-responsables",
    f"{WEB_BASE}/es/pagina/otros-planes",
    f"{WEB_BASE}/es/pagina/sector-industrial-1",
    f"{WEB_BASE}/es/pagina/sector-industrial-3",
    f"{WEB_BASE}/es/pagina/planeamiento-san-cristobal-tramitacion",
    f"{WEB_BASE}/es/pagina/auditoria-urbanistica-monte-jucar",
    f"{WEB_BASE}/es/pagina/constitucion-entidad-gestion-modernizacion-poligono-industrial-2",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra|llicencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|edicto|dogv|bop|ordenanza|sector|urbanizaci[oó]n|"
    r"industrial|residencial|entorn|convenio|programaci[oó]n|homologaci[oó]n|"
    r"auditor[ií]a|monte j[uú]car|san crist[oó]bal|gesti[oó]n urban)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"morosidad|pmp web|padron|ii+aee|calendari fiscal|jurado|premios excelencia|"
    r"escoleta|ecovidrio|fragments)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ANUNCIO_ID = re.compile(r"anuncio\.aspx\?id=(\d+)", re.I)
RE_DOC_LINK = re.compile(
    r'href="((?:https://alberic\.sede\.dival\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.alberic\.es)?/sites/www\.alberic\.es/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PAGE_HREF = re.compile(r'href="(/es/(?:pagina|seccion)/[^"#?]+)"', re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("es", "und", "va", "ca"):
            if value.get(key):
                return str(value[key])
        for v in value.values():
            if v:
                return str(v)
        return ""
    return str(value or "")


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
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or re.search(r"sector\s+[ivx\d-]+", n):
        return "plan parcial"
    if "pgou" in n or "plan general" in n or "normas urban" in n:
        return "PGOU"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "convenio" in n:
        return "convenio urbanístico"
    if "auditor" in n:
        return "auditoría urbanística"
    if "entorn" in n and "rehabilit" in n:
        return "entorno rehabilitación programada"
    if "informaci" in n or "edicto" in n or "dogv" in n:
        return "información pública"
    if "licencia" in n or "llicencia" in n:
        return "licencia publicada"
    if "programaci" in n:
        return "programación sectorial"
    return "urbanismo"


def _pdf_title(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:500] or url


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


class AlbericAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + transparencia DigitalValue + sede Dival + ICV WFS partial."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparency_base = str(self.config.get("transparency_base") or TRANSPARENCY_BASE).rstrip("/")
        self.api_base = str(self.config.get("api_base") or API_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.transparency_urbanismo_url = str(
            self.config.get("transparency_urbanismo_url") or TRANSPARENCY_URBANISMO_URL
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 20))
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_type = str(geom_cfg.get("type_name") or GVA_WFS_TYPE)
        self.gva_offsets = list(geom_cfg.get("offsets") or GVA_WFS_OFFSETS)
        self.user_agent = str(self.config.get("user_agent", "poc-bocm-alberic/1.0"))
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.web_base}{href if href.startswith('/') else '/' + href}"

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _transparency_article_url(self, item: dict[str, Any]) -> str:
        data = item.get("data") or {}
        slug = _localized(data.get("slug") or item.get("slug") or "")
        if slug:
            return f"{self.transparency_base}/es/transparencia/{slug.strip('/')}"
        return f"{self.transparency_base}/es/transparencia/{item.get('_id', '')}"

    def _file_url(self, file_ref: Any) -> str | None:
        if isinstance(file_ref, dict):
            fid = file_ref.get("file") or file_ref.get("_id")
            title = _localized(file_ref.get("title")) or None
        else:
            fid = str(file_ref)
            title = None
        if not fid:
            return None
        return f"https://cdn.digitalvalue.es/alberic/assets2/{fid}"

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, timeout=60)
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
            html = self._fetch(url, timeout=60)
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

    def _collect_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        ns = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml"}

        for start in self.gva_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "request": "GetFeature",
                    "version": "2.0.0",
                    "typeName": self.gva_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.gva_wfs}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                continue

            for member in root.findall(".//wfs:member", ns):
                feat_el = member[0]
                props: dict[str, str] = {}
                geom = None
                for child in feat_el:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        pos = child.find(".//gml:posList", ns)
                        if pos is not None and pos.text:
                            geom = _gml_poslist_to_polygon(pos.text)
                    else:
                        props[tag] = (child.text or "").strip()

                if props.get("cod_ine_mun") != INE_COD_MUN:
                    continue
                if not geom:
                    continue

                label = props.get("denominaci") or props.get("expediente") or ""
                key = f"{props.get('expediente')}:{label}"
                if key in seen:
                    continue
                seen.add(key)
                feats.append(
                    {
                        "label": label,
                        "expediente": props.get("expediente") or "",
                        "geom": geom,
                        "source_url": (
                            f"{self.gva_wfs}?service=WFS&request=GetFeature&"
                            f"startIndex={start}&count=500"
                        ),
                    }
                )

        self._gva_cache = feats
        return feats

    def _match_gva_keywords(self, title: str) -> list[str]:
        low = (title or "").lower()
        keys: list[str] = []
        for token in (
            "plan general",
            "pgou",
            "sector vi",
            "sector vii",
            "sector i-3",
            "sector i-2",
            "sector i-1",
            "industrial",
            "modificaci",
            "san cristobal",
            "monte jucar",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        keys = self._match_gva_keywords(titulo)
        if not keys:
            return None

        feats = self._collect_gva_features()
        if not feats:
            return None

        title_low = titulo.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for feat in feats:
            label = (feat.get("label") or "").lower()
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 1.0
            if "plan general" in title_low and "plan general" in label:
                score += 2.0
            if "sector vi" in title_low and "sector vi" in label:
                score += 2.0
            if "sector vii" in title_low and "sector vii" in label:
                score += 2.0
            if score <= 0:
                continue
            candidates.append((score, feat, feat.get("source_url") or self.gva_wfs))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        best_score, best_feat, source_url = candidates[0]
        matched = [f["geom"] for f in feats if f.get("geom")]
        if "plan general" in title_low or "pgou" in title_low:
            matched = [f["geom"] for f in feats if "plan general" in (f.get("label") or "").lower()]
        elif "sector vi" in title_low:
            matched = [f["geom"] for f in feats if "sector vi" in (f.get("label") or "").lower()]
        elif "sector vii" in title_low:
            matched = [f["geom"] for f in feats if "sector vii" in (f.get("label") or "").lower()]
        geom = _merge_geometries(matched) or best_feat.get("geom")
        if not geom:
            return None

        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
            "coord_source": "portal_geometry_centroid",
        }

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

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        pdf_urls: set[str] = set()
        page_urls: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            page_urls.add(url)
            for m in RE_PDF_HREF.finditer(html):
                pdf_urls.add(self._abs_web(m.group(1)))
            if len(visited) < self.max_crawl_pages:
                for m in RE_PAGE_HREF.finditer(html):
                    page = self._abs_web(m.group(1))
                    low = page.lower()
                    if any(
                        k in low
                        for k in (
                            "urban",
                            "plan",
                            "sector",
                            "licenc",
                            "gestion",
                            "tramit",
                            "industrial",
                            "plane",
                        )
                    ):
                        if page not in visited:
                            queue.append(page)

        rows: list[dict[str, Any]] = []
        for page in sorted(page_urls):
            title = page.rsplit("/", 1)[-1].replace("-", " ").title()
            rec: dict[str, Any] = {
                "id": _stable_id("proy", page),
                "municipio": MUNICIPIO,
                "titulo": f"Urbanismo — {title}"[:500],
                "fecha": None,
                "tipo": "planeamiento",
                "url": page,
                "source": "ayuntamiento",
                "origen": "web_pagina",
            }
            self._enrich_geometry(rec)
            rows.append(rec)

        for pdf in sorted(pdf_urls):
            titulo = _pdf_title(pdf)
            rec = {
                "id": _stable_id("proy", pdf),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(titulo),
                "tipo": _proyecto_tipo(titulo),
                "url": pdf,
                "source": "ayuntamiento",
                "origen": "web_pdf",
                "pdf_url": pdf,
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _walk_transparency_nodes(self, nodes: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                continue
            title = _localized(node.get("title"))
            body = _strip_html(_localized(node.get("body")))
            blob = f"{title} {body}"
            url = self._transparency_article_url(node)
            fecha = None
            raw_date = node.get("date") or node.get("updated")
            if raw_date:
                fecha = str(raw_date).split("T", 1)[0]
            if not fecha:
                fecha = _fecha_from_blob(blob)

            file_urls: list[str] = []
            for group in node.get("filesGroup") or []:
                for file_ref in group.get("files") or []:
                    furl = self._file_url(file_ref)
                    if furl:
                        file_urls.append(furl)

            if title and (RE_PROYECTO.search(blob) or file_urls):
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": file_urls[0] if file_urls else url,
                    "source": "ayuntamiento",
                    "origen": "transparencia",
                }
                if file_urls:
                    rec["pdf_url"] = file_urls[0]
                self._enrich_geometry(rec)
                rows.append(rec)

            for group in node.get("nodesGroup") or []:
                self._walk_transparency_nodes(group.get("nodes") or [], rows)

    def _collect_transparency_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        hub_ids = [
            "5bd6c98bb76d34863ac194df",  # informacion urbanistica
            "6537b463a6b09769efac6f97",  # convenio actuaciones urbanas
        ]
        for article_id in hub_ids:
            try:
                item = self._fetch_json(f"{self.api_base}/articulos/{article_id}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                self._walk_transparency_nodes([item], rows)

        offset = 0
        while offset < 400:
            try:
                data = self._fetch_json(
                    f"{self.api_base}/articulos?nodeTypes=/transparencia/i&limit=200&offset={offset}"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("items") or []
            if not batch:
                break
            for item in batch:
                title = _localized(item.get("title"))
                blob = title.lower()
                if not any(
                    k in blob
                    for k in ("plane", "urban", "plan", "industrial", "convenio", "entorn", "gestion")
                ):
                    continue
                self._walk_transparency_nodes([item], rows)
            if len(batch) < 200:
                break
            offset += 200
        return rows

    def _collect_gva_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_url = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for feat in self._collect_gva_features():
            label = feat.get("label") or ""
            exp = feat.get("expediente") or ""
            titulo = f"{label} (exp. {exp})" if exp and exp != "00000000" else label
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"gva:{exp}:{label}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_blob(exp),
                "tipo": _proyecto_tipo(label),
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "gva_wfs",
                "expte": exp or None,
            }
            geom = feat.get("geom")
            if geom:
                rec.update(
                    {
                        "geom_geojson": geom,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": feat.get("source_url") or self.gva_wfs,
                        "coord_source": "portal_geometry_centroid",
                    }
                )
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
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
                "titulo": "Tablón de anuncios — sede electrónica Alberic",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en alberic.sede.dival.es",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Instancia general y trámites administrativos; licencias presencial/sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/es/pagina/tramitaciones-licencias-declaraciones-responsables"),
                "fecha_concesion": None,
                "tipo": "formularios licencias y DR",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tramitaciones licencias y declaraciones responsables",
                "url": f"{self.web_base}/es/pagina/tramitaciones-licencias-declaraciones-responsables",
                "source": "ayuntamiento",
                "nota": "Formularios PDF en web municipal Drupal",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.transparency_urbanismo_url),
                "fecha_concesion": None,
                "tipo": "planeamiento y transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Planeamiento urbanístico — portal transparencia",
                "url": self.transparency_urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Instrumentos de planeamiento e ICV/GVA",
                "origen": "transparencia",
            },
        ]

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
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite", "transparencia")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
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

        for rec in self._collect_gva_proyectos():
            add(rec)
        for rec in self._collect_web_proyectos():
            add(rec)
        for rec in self._collect_transparency_proyectos():
            add(rec)
        for item in self._collect_tablon_rss():
            enriched = self._enrich_anuncio_docs(item)
            add(self._tablon_to_proyecto(enriched))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "gva_wfs": sum(1 for r in rows if r.get("origen") == "gva_wfs"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
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
