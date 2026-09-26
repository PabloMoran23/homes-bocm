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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.alfarrasi.es"
SEDE_BASE = "https://alfarrasi.sede.dival.es"
MUNICIPIO = "Alfarrasí"
ID_PREFIX = "alfarrasi"
INE_COD_MUN = "46027"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
URBANISMO_URL = f"{WEB_BASE}/es/transparencia/informacio-urbanistica"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("Planeamiento.Zonificacion", "Zonificacion"),
    ("ms:InventarioSuSuz", "InventarioSuSuz"),
)
GVA_WFS_OFFSETS = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500]

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WEB_BASE}/es/transparencia/modificaciones-aprobadas-al-pgou",
    f"{WEB_BASE}/es/transparencia/convenis-urbanistics",
    f"{WEB_BASE}/es/transparencia/urbanismo",
    f"{WEB_BASE}/es/transparencia/modificacions-reformes-complementaries",
]

STATIC_DOC_SEEDS: list[tuple[str, str]] = [
    ("Modificació Puntual nº 5 PGOU", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n1.pdf"),
    ("Modificació reparcelació forçosa sector sud est", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n2.pdf"),
    ("Urbanització sector sud residencial", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n3.pdf"),
    (
        "Llicència ambiental per a emmagatzematge temporal i venta major de productes de recuperació o reciclatge de plàstics",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n4.pdf",
    ),
    ("MODIFICACIÓ Nº 6 PGOU (modificacions 4 i 5)", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n5.pdf"),
    ("MODIFICACIÓ Nº 6 PGOU (àrees d'actuació)", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n6.pdf"),
    ("MODIFICACIÓ Nº 6 PGOU (pla d'ordenació)", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n7.pdf"),
    ("MODIFICACIÓ Nº 6 PGOU (text refòs)", f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/n8.pdf"),
]

STATIC_LICENCIA_SEEDS: list[tuple[str, str]] = [
    (
        "SOL·LICITUT D'OBRA MENOR I OCUPACIÓ DE VIA PÚBLICA",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/solicitud_de_obra_menor_y_ocupacion_de_via_publica.pdf",
    ),
    (
        "SOL·LICITUT DE OBRA MAJOR I OCUPACIÓ DE VIA PÚBLICA",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/solicitud_de_obra_mayor_y_ocupupacion_de_via_publica.pdf",
    ),
    (
        "SOL·LICITUT DE LLICÈNCIA SEGONA OCUPACIÓ",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/solicitud_de_licencia_segunda_ocupacion.pdf",
    ),
    (
        "SOL·LICITUT DE LLICÈNCIA PRIMERA OCUPACIÓ",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/solicitud_de_licencia_primera_ocupacion.pdf",
    ),
    (
        "DECLARACIÓ RESPONSABLE D'OBRA MENOR, OCUPACIÓ DE VIA PÚBLICA I SUBSÒL",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/declaracion_responsable_de_obra_menor_ocupacion_de_via_publica_y_subsuelo.pdf",
    ),
    (
        "DECLARACIÓ RESPONSABEL D'OBRA MENOR I OCUPACIÓ DE VIA PÚBLICA",
        f"{WEB_BASE}/sites/www.alfarrasi.es/files/documents/field_collection_item/1313/declaracion_responsabel_de_obra_menor_y_ocupacion_de_via_publica.pdf",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|segona ocupaci[oó]n|segunda ocupaci[oó]n|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|edicto|ordenanza|sector|urbanizaci[oó]n|urbanitzaci|"
    r"pol[ií]gono|ambiental|licencia ambiental)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|iae|taxi|cheque beb|angelet de la corda|ayudas estudiantes|"
    r"delegaci[oó]n de las distintas|junta de gobierno|declaraci[oó]n de bienes)",
)
RE_DOC_LINK = re.compile(
    r'href="((?:https://alfarrasi\.sede\.dival\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.alfarrasi\.es)?/sites/www\.alfarrasi\.es/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:sector|pol[ií]gono|poligon)\s+(?:sur|nord|norte|oest|este|est)[\w\s\-]*|"
    r"modificaci[oó]n\s+n[ºo°]?\s*\d+|pgou)\b",
)

GML_NS = {
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "reparcel" in n:
        return "reparcelación forzosa"
    if "plan parcial" in n or "sector" in n or "polígono" in n or "poligon" in n:
        return "plan parcial / sector"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "licencia ambiental" in n or "ambiental" in n:
        return "licencia ambiental"
    if "urbanitzaci" in n or "urbanizaci" in n:
        return "urbanización"
    if "ordenanza" in n:
        return "ordenanza urbanística"
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


class AlfarrasiAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede Dival (Sedipualba) + ICV GVA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_offsets = list(geom_cfg.get("offsets") or GVA_WFS_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_COD_MUN)
        self._gva_cache: list[dict[str, Any]] | None = None
        self._gva_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alfarrasi/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.75 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alfarrasi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_web(self, href: str) -> str:
        return unescape(urljoin(f"{self.web_base}/", href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

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
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            fecha = None
            pub = item.findtext("pubDate") or ""
            if pub:
                try:
                    fecha = datetime.strptime(pub.strip()[:25].strip(), "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
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

    def _parse_wfs_member(self, member: ET.Element, layer_tag: str) -> dict[str, Any] | None:
        feat = None
        for child in member:
            tag = child.tag.split("}")[-1]
            if tag == layer_tag or tag in ("InventarioSuSuz", "Zonificacion"):
                feat = child
                break
        if feat is None:
            return None

        props: dict[str, str] = {}
        geom = None
        for child in feat:
            tag = child.tag.split("}")[-1]
            if tag == "msGeometry":
                pos = child.find(".//gml:posList", GML_NS)
                if pos is not None and pos.text:
                    geom = _gml_poslist_to_polygon(pos.text)
            else:
                props[tag] = (child.text or "").strip()

        if props.get("cod_ine_mun") != self.cod_ine_mun:
            return None

        label = (
            props.get("denominaci")
            or props.get("denominaci_val")
            or props.get("pp")
            or props.get("ue")
            or props.get("expediente")
            or ""
        )
        ue = props.get("ue") or ""
        pp = props.get("pp") or ""
        titulo = label.strip()
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Ámbito {props.get('id', 'WFS')}"

        return {
            "titulo": titulo[:500],
            "fecha": props.get("f_aprob") or props.get("f_public") or None,
            "label": label,
            "pp": pp or None,
            "ue": ue or None,
            "expediente": props.get("expediente") or None,
            "clasificacion": props.get("clasificacion") or None,
            "geom": geom,
            "wfs_id": f"{layer_tag}:{props.get('id', label)}",
            "source_url": self.gva_wfs,
            "origen": "icv_wfs",
        }

    def _collect_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer_tag in GVA_WFS_LAYERS:
            for start in self.gva_offsets:
                params = urllib.parse.urlencode(
                    {
                        "service": "WFS",
                        "request": "GetFeature",
                        "version": "2.0.0",
                        "typeName": type_name,
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
                members = root.findall(".//wfs:member", GML_NS)
                if not members:
                    continue
                for member in members:
                    rec = self._parse_wfs_member(member, layer_tag)
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        feats.append(rec)

        self._gva_cache = feats
        self._gva_by_key = {}
        for rec in feats:
            for key in (rec.get("titulo") or "", rec.get("label") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if len(low) >= 4:
                    self._gva_by_key[low] = rec
            for m in RE_SECTOR_TOKEN.finditer(rec.get("titulo") or ""):
                self._gva_by_key[m.group(1).lower()] = rec
        return feats

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._gva_by_key is None:
            self._collect_gva_features()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._gva_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        if "plan general" in low or "pgou" in low:
            for rec in self._collect_gva_features():
                if "plan general" in (rec.get("titulo") or "").lower():
                    return rec
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit or not hit.get("geom"):
            return
        geom = hit["geom"]
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            f"{self.gva_wfs}?service=WFS&request=GetFeature&typeName=Planeamiento.Zonificacion"
            f"&CQL_FILTER=cod_ine_mun='{self.cod_ine_mun}'"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec.setdefault("lat", centroid[0])
            rec.setdefault("lon", centroid[1])

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for titulo, url in STATIC_DOC_SEEDS:
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(titulo),
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": "drupal_static",
            }
            self._attach_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=60)
            except urllib.error.URLError:
                continue
            page_title = _strip_html(re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S).group(1)) if re.search(r"<h1", html, re.I) else page_url
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                doc_url = self._abs_web(href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                link_title = ""
                title_m = re.search(
                    rf'href="{re.escape(href)}"[^>]*>([^<]+)',
                    html,
                    re.I,
                )
                if title_m:
                    link_title = _strip_html(title_m.group(1))
                titulo = link_title or Path(doc_url).name
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": doc_url,
                    "page_url": page_url,
                    "blob": f"{titulo} {page_title}",
                    "origen": "drupal_crawl",
                }
                rows.append(rec)
        return rows

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._collect_gva_features():
            rec: dict[str, Any] = {
                "id": _stable_id("proy", feat["wfs_id"]),
                "municipio": MUNICIPIO,
                "titulo": feat["titulo"],
                "fecha": feat.get("fecha"),
                "tipo": _proyecto_tipo(feat["titulo"]),
                "url": feat.get("source_url") or self.gva_wfs,
                "source": "ayuntamiento",
                "origen": feat.get("origen"),
                "wfs_id": feat.get("wfs_id"),
            }
            if feat.get("pp"):
                rec["pp"] = feat["pp"]
            if feat.get("ue"):
                rec["ue"] = feat["ue"]
            if feat.get("geom"):
                rec["geom_geojson"] = feat["geom"]
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = feat.get("source_url") or self.gva_wfs
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(feat["geom"])
                if centroid:
                    rec["lat"], rec["lon"] = centroid
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
                "titulo": "Tablón de anuncios — sede electrónica Alfarrasí",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en alfarrasi.sede.dival.es",
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
                "nota": "Sin trámites urbanísticos en línea; licencias presencial/sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Informació urbanística — transparencia municipal",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF de licencias y modificaciones PGOU",
                "origen": "web_tramite",
            },
        ]

    def _collect_static_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for titulo, url in STATIC_LICENCIA_SEEDS:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "formulario trámite",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Formulario informativo; sin registro público de concesiones",
                    "origen": "drupal_static",
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
        rec: dict[str, Any] = {
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
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or row.get("blob") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("url") or blob),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec = self._to_proyecto(row)
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info_pages():
            add(rec)
        for rec in self._collect_static_licencias():
            add(rec)
        for item in self._collect_tablon_rss():
            add(self._tablon_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite", "drupal_static")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for rec in self._collect_static_proyectos():
            add(rec)
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))
        for item in self._collect_tablon_rss():
            enriched = self._enrich_anuncio_docs(item)
            add(self._tablon_to_proyecto(enriched))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
