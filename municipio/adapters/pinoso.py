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

WEB_BASE = "https://www.pinoso.es"
SEDE_BASE = "https://pinoso.sedipualba.es"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
TRAMITES_URL = f"{WEB_BASE}/el-ayuntamiento/tramites-y-gestiones/"
URBANISMO_URL = (
    f"{WEB_BASE}/el-ayuntamiento/concejalias/concejalia-mantenimiento-y-orden-urbano/"
)
EADMIN_URL = "https://sede.pinoso.es"
MUNICIPIO = "Pinoso"
ID_PREFIX = "pinoso"
INE_COD_MUN = "03095"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_SUZ = "InventarioSuSuz"
GVA_WFS_ZON = "Planeamiento.Zonificacion"
GVA_ZON_OFFSETS = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000]

WP_SEARCH_TERMS = (
    "urbanismo",
    "planeamiento",
    "estudio de detalle",
    "plan parcial",
    "poligono industrial",
    "reparto",
    "licencia obra",
)

DEFAULT_TRAMITE_PDFS: list[dict[str, str]] = [
    {
        "titulo": "Solicitud Licencia de Obra Menor",
        "url": f"{WEB_BASE}/wp-content/uploads/Solicitud-Licencia-de-Obra-Menor-2024-presupuesto-1-1.pdf",
    },
    {
        "titulo": "Obras mayores — documentación albañil inicio obra",
        "url": f"{WEB_BASE}/wp-content/uploads/OBRAS-MAYORES-DOC-ALBANIL-INICIO-OBRA_editable-1-2.pdf",
    },
    {
        "titulo": "Solicitud licencia de actividad",
        "url": f"{WEB_BASE}/wp-content/uploads/SOLICITUD-LICENCIA-DE-ACTIVIDAD-2024-3-2.pdf",
    },
    {
        "titulo": "Comunicación inicio obras agua potable parcela rústica",
        "url": (
            f"{WEB_BASE}/wp-content/uploads/"
            "03-AGUAS-DOC-1-COMUNICACION-INICIO-OBRAS-AGUA-POTABLE-EN-PARCELA-RUSTICA-1.pdf"
        ),
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|edicto|bop|ordenanza|sector|urbanizaci[oó]n|"
    r"estudio de detalle|reparto|pol[ií]gono industrial|marjal|saladar|tossal|"
    r"impacto ambiental|iate|suz|snu)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa|proceso selectivo|conserje|administrativo|trabajo social|"
    r"cobranza iae|plan antifraude|acta.*fase)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ANUNCIO_ID = re.compile(r"anuncio\.aspx\?id=(\d+)", re.I)
RE_DOC_LINK = re.compile(
    r'href="((?:https://pinoso\.sedipualba\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_WP_ENTRY = re.compile(
    r'class="entry-title"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_WP_DATE = re.compile(r'<time[^>]+datetime="((?:19|20)\d{2}-\d{2}-\d{2})', re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_text(text: str) -> str | None:
    m = RE_WP_DATE.search(text or "")
    if m:
        return m.group(1)
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n or re.search(r"\bpp\s*\d", n):
        return "plan parcial"
    if "plan especial" in n or "suz" in n:
        return "plan especial"
    if "mod" in n and ("pg" in n or "plan general" in n):
        return "modificación PGOU"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "polígono industrial" in n or "poligono industrial" in n:
        return "polígono industrial"
    if "reparto" in n or "área de reparto" in n:
        return "área de reparto"
    if "impacto ambiental" in n or "iate" in n:
        return "evaluación ambiental"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "edicto" in n or "bop" in n:
        return "edicto / información pública"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


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


class PinosoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress pinoso.es + sede Sedipualba tablón RSS + ICV WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.eadmin_url = str(self.config.get("eadmin_url") or EADMIN_URL).rstrip("/")
        self.tramite_pdfs: list[dict[str, str]] = list(
            self.config.get("tramite_pdfs") or DEFAULT_TRAMITE_PDFS
        )
        self.wp_search_terms = tuple(self.config.get("wp_search_terms") or WP_SEARCH_TERMS)
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_suz_type = str(geom_cfg.get("suz_type_name") or GVA_WFS_SUZ)
        self.gva_zon_type = str(geom_cfg.get("zon_type_name") or GVA_WFS_ZON)
        self.gva_zon_offsets = list(geom_cfg.get("zon_offsets") or GVA_ZON_OFFSETS)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_COD_MUN)
        self._suz_cache: list[dict[str, Any]] | None = None
        self._zon_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pinoso/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pinoso/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

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
        out = dict(row)
        if docs:
            out["pdf_url"] = docs[0]
            out["documentos"] = docs
        fecha = _parse_fecha_dmy(html)
        if fecha:
            out["fecha"] = fecha
        return out

    def _parse_wfs_member(self, feat_el: ET.Element) -> dict[str, Any] | None:
        props: dict[str, str] = {}
        geom = None
        for child in feat_el:
            tag = child.tag.split("}")[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}")[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if props.get("cod_ine_mun") != self.ine_mun:
            return None
        label = props.get("denominaci") or props.get("pp") or props.get("clasificacion") or ""
        if not label:
            return None
        return {
            "label": label,
            "expediente": props.get("expediente") or props.get("id") or "",
            "clasificacion": props.get("clasificacion") or "",
            "fecha": props.get("f_aprob") or props.get("f_public"),
            "geom": geom,
        }

    def _collect_suz_features(self) -> list[dict[str, Any]]:
        if self._suz_cache is not None:
            return self._suz_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        start = 0
        step = 200
        while True:
            url = (
                f"{self.gva_wfs}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typename={self.gva_suz_type}&outputFormat=GML3&srsName=EPSG:4326"
                f"&count={step}&STARTINDEX={start}"
            )
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = [el for el in root if el.tag.endswith("member")]
            if not members:
                break
            for member in members:
                parsed = self._parse_wfs_member(member[0])
                if not parsed:
                    continue
                key = f"{parsed.get('label')}:{parsed.get('expediente')}"
                if key in seen:
                    continue
                seen.add(key)
                parsed["source_url"] = url
                feats.append(parsed)
            start += step
            if len(members) < step:
                break

        self._suz_cache = feats
        return feats

    def _collect_zon_features(self) -> list[dict[str, Any]]:
        if self._zon_cache is not None:
            return self._zon_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        ns = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml"}

        for start in self.gva_zon_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "request": "GetFeature",
                    "version": "2.0.0",
                    "typeName": self.gva_zon_type,
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
                parsed = self._parse_wfs_member(member[0])
                if not parsed or not parsed.get("geom"):
                    continue
                key = f"{parsed.get('expediente')}:{parsed.get('label')}"
                if key in seen:
                    continue
                seen.add(key)
                parsed["source_url"] = url
                feats.append(parsed)

        self._zon_cache = feats
        return feats

    def _match_keywords(self, title: str) -> list[str]:
        low = (title or "").lower()
        keys: list[str] = []
        for token in (
            "plan general",
            "pgou",
            "marjal",
            "saladar",
            "tossal",
            "patins",
            "furs",
            "germanies",
            "estudio de detalle",
            "reparto",
            "ea-8",
            "industrial",
            "modificaci",
            "ordenanza",
            "sector",
            "pp1",
            "pp2",
            "ua1",
            "ua2",
            "ua3",
            "ua4",
            "ua5",
            "s1",
            "s2",
            "s3",
            "s4",
            "s5",
            "s6",
            "s7",
            "s8",
            "s9",
            "s10",
            "s11",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_keywords(title)
        if not keys:
            return None

        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []

        for feat in self._collect_suz_features() + self._collect_zon_features():
            label = (feat.get("label") or "").lower()
            if not feat.get("geom"):
                continue
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 1.0
            if "plan general" in title_low and "plan general" in label:
                score += 2.0
            if score <= 0:
                continue
            candidates.append((score, feat, feat.get("source_url") or self.gva_wfs))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        best_score, best_feat, source_url = candidates[0]
        matched = [f["geom"] for _, f, _ in candidates if f.get("geom")]
        if "plan general" in title_low or "pgou" in title_low:
            matched = [
                f["geom"]
                for f in self._collect_zon_features()
                if "plan general" in (f.get("label") or "").lower() and f.get("geom")
            ]
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

    def _collect_wp_search(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for term in self.wp_search_terms:
            url = f"{self.web_base}/?s={urllib.parse.quote(term)}"
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            for m in RE_WP_ENTRY.finditer(html):
                link = m.group(1).strip()
                title = _strip_html(m.group(2))
                if not link or link in seen_urls:
                    continue
                if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                    continue
                seen_urls.add(link)
                snippet = html[m.start() : m.start() + 800]
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": _fecha_from_text(snippet),
                        "blob": title,
                        "origen": "wp_noticia",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows = [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Pinoso",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en pinoso.sedipualba.es",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede Sedipualba",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Trámites administrativos sin histórico de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites y gestiones urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones — formularios licencias",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Impresos licencia obra menor, actividad y obras mayores",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.eadmin_url),
                "fecha_concesion": None,
                "tipo": "sede eAdmin",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin (sede.pinoso.es)",
                "url": self.eadmin_url,
                "source": "ayuntamiento",
                "nota": "Registro y carpeta ciudadano; tablón provincial Diputación Alicante",
                "origen": "sede_tramite",
            },
        ]
        for pdf in self.tramite_pdfs:
            titulo = str(pdf.get("titulo") or "").strip()
            url = str(pdf.get("url") or "").strip()
            if not titulo or not url:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "formulario licencia / obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Impreso descargable en web municipal",
                    "origen": "web_tramite",
                }
            )
        return rows

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

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "wp_noticia",
        }
        self._enrich_geometry(rec)
        return rec

    def _collect_planeamiento_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for feat in self._collect_suz_features():
            label = (feat.get("label") or "").strip()
            if not label:
                continue
            exp = feat.get("expediente") or ""
            clas = feat.get("clasificacion") or ""
            titulo = f"{label} ({clas})" if clas else label
            if exp and exp != "00000000":
                titulo = f"{titulo} (exp. {exp})"
            key = f"suz:{label}:{exp}"
            if key in seen:
                continue
            seen.add(key)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_text(str(feat.get("fecha") or "")),
                "tipo": _proyecto_tipo(label),
                "url": feat.get("source_url") or self.gva_wfs,
                "source": "ayuntamiento",
                "origen": "icv_suz",
                "expte": exp or None,
            }
            if feat.get("geom"):
                rec["geom_geojson"] = feat["geom"]
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = feat.get("source_url") or self.gva_wfs
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(feat["geom"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)

        for feat in self._collect_zon_features():
            label = (feat.get("label") or "").strip()
            if not label:
                continue
            exp = feat.get("expediente") or ""
            key = f"zon:{exp}:{label}"
            if key in seen:
                continue
            seen.add(key)
            titulo = f"{label} (exp. {exp})" if exp and exp != "00000000" else label
            rec = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(label),
                "url": feat.get("source_url") or self.gva_wfs,
                "source": "ayuntamiento",
                "origen": "icv_zon",
                "expte": exp or None,
            }
            if feat.get("geom"):
                rec["geom_geojson"] = feat["geom"]
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = feat.get("source_url") or self.gva_wfs
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(feat["geom"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)

        return rows

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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
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

        for item in self._collect_tablon_rss():
            enriched = self._enrich_anuncio_docs(item)
            add(self._tablon_to_proyecto(enriched))

        for item in self._collect_wp_search():
            add(self._wp_to_proyecto(item))

        for seed in self._collect_planeamiento_seeds():
            add(seed)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
            "wp_noticia": sum(1 for r in rows if r.get("origen") == "wp_noticia"),
            "icv_suz": sum(1 for r in rows if r.get("origen") == "icv_suz"),
            "icv_zon": sum(1 for r in rows if r.get("origen") == "icv_zon"),
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
