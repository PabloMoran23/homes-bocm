from __future__ import annotations

import hashlib
import json
import re
import ssl
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

SEDE_BASE = "https://sede.paterna.es"
SEARCH_URL = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica_search.action"
TABLON_INDEX = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica.action?edictos=1"
TRAMITES_CATALOGO = f"{SEDE_BASE}/opensiac/informacionpublica/tramites_enter.action"
LICENCIA_OBRA_TRAMITE = (
    f"{SEDE_BASE}/opensiac/informacionpublica/tramitesinfo?tramitesInfoForm.id=324"
)
LICENCIA_USOS_TRAMITE = (
    f"{SEDE_BASE}/opensiac/informacionpublica/tramitesinfo?tramitesInfoForm.id=293"
)
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
MUNICIPIO = "Paterna"
ID_PREFIX = "paterna"
INE_MUN = "46190"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"
ICV_WFS_START = 7000
ICV_WFS_MAX_START = 11000

SEARCH_TERMS = [
    "PGOU",
    "PLAN GENERAL",
    "MODIFIC",
    "URBAN",
    "LICENC",
    "SECTOR",
    "EXPROPI",
    "INFORMACION PUBLICA",
    "REPARCEL",
    "PRI",
    "PUAM",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|inicio de obra|obra (?:mayor|menor)|"
    r"legalizaci[oó]n|apertura.*local|actividad econ[oó]mica|licencia ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de reforma interior)|pgou|puam|"
    r"convenio|informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|expropiaci[oó]n|reforma interior|suz|unidad de actuaci)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|oferta de empleo|bolsa de trabajo|subvenci[oó]n|"
    r"cheque beb[eé]|cheque empleo|bono comercio|jjdd|premios al comercio|"
    r"padrones cobratorios|iae|plantilla org[aá]nica|orden del d[ií]a jgl|"
    r"pleno sesi[oó]n|bando sobre padrones|distinciones m[eé]rito ling[uü][ií]stico)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LISTING_ROW = re.compile(
    r"infopublica_ver\.action[^\"]*id=(\d+)\"[^>]*title=\"Mostrar ([^\"]+)\"",
    re.I,
)
RE_LISTING_TABLE_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(\d{2}/\d{2}/\d{4})</td>",
    re.I | re.S,
)
RE_DETAIL_FIELD = re.compile(
    r'<td class="Etiqueta">([^<]+)</td>\s*<td class="Descripcion">(.*?)</td>',
    re.I | re.S,
)
RE_PDF_LINK = re.compile(
    r'href="(/opensiac/informacionpublica/infopublica_descargar\.action[^"]+)"',
    re.I,
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|SECTOR|UA|MODIFICACI[oó]N)[\s\-]?(?:PUNTUAL|N\.?\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml/3.2",
    "gml32": "http://www.opengis.net/gml",
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
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("pgou" in n or "plan general" in n):
        return "modificación PGOU"
    if "plan de reforma interior" in n or re.search(r"\bpri\b", n):
        return "plan de reforma interior"
    if "puam" in n:
        return "plan urbanístico de actuación municipal"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "expropiaci" in n:
        return "expropiación"
    if "reparcel" in n:
        return "reparcelación"
    if "licencia ambiental" in n:
        return "licencia ambiental"
    if "licencia" in n:
        return "licencia publicada"
    if "sector" in n:
        return "sector planeamiento"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    parts = [float(x) for x in poslist.split() if x.strip()]
    if len(parts) < 6:
        return None
    coords: list[list[float]] = []
    for i in range(0, len(parts) - 1, 2):
        lat, lon = parts[i], parts[i + 1]
        coords.append([lon, lat])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//{http://www.opengis.net/gml}Polygon")
    if poly is None:
        poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//{http://www.opengis.net/gml}posList")
    if pos is None:
        pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class PaternaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenSIAC sede.paterna.es + ICV WFS planeamiento (cod_ine_mun=46190)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.search_url = str(self.config.get("search_url") or SEARCH_URL)
        self.search_terms = [str(t) for t in (self.config.get("search_terms") or SEARCH_TERMS)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        self.icv_start = int(self.config.get("icv_wfs_start") or ICV_WFS_START)
        self.icv_max_start = int(self.config.get("icv_wfs_max_start") or ICV_WFS_MAX_START)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, timeout: int = 120) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-paterna/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "iso-8859-15"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href.replace("&amp;", "&")))

    def _search_publications(
        self,
        *,
        edictos: str,
        descripcion_tipo: str,
        referencia: str,
        descripcion: str | None = None,
        todos: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "edictos": edictos,
            "descripcionTipoTablon": descripcion_tipo,
            "referencia": referencia,
        }
        if todos:
            params["botonTodos"] = "Todos"
        elif descripcion:
            params["descripcionPublicacion"] = descripcion
            params["botonBuscar"] = "Buscar"
        data = urllib.parse.urlencode(params).encode("iso-8859-15", errors="replace")
        try:
            html = self._fetch(self.search_url, data=data)
        except urllib.error.URLError:
            return []
        return self._parse_listing_html(html, origen="tablon_opensiac", edictos=edictos)

    def _parse_listing_html(
        self, html: str, *, origen: str, edictos: str | None = None
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LISTING_ROW.finditer(html):
            pub_id, titulo = m.group(1), _strip_html(m.group(2))
            if pub_id in seen:
                continue
            seen.add(pub_id)
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": f"{self.sede_base}/opensiac/informacionpublica/infopublica_ver.action?id={pub_id}",
                    "blob": titulo,
                    "origen": origen,
                    "edictos": edictos,
                }
            )
        for m in RE_LISTING_TABLE_ROW.finditer(html):
            title_html, fecha_raw = m.group(1), m.group(2)
            if "infopublica_ver" not in title_html:
                continue
            id_m = re.search(r"id=(\d+)", title_html)
            if not id_m:
                continue
            pub_id = id_m.group(1)
            titulo = _strip_html(re.sub(r"<a[^>]*>", " ", title_html))
            for row in rows:
                if row["pub_id"] == pub_id:
                    row["fecha"] = _parse_fecha_dmy(fecha_raw)
                    if titulo:
                        row["titulo"] = titulo[:500]
                        row["blob"] = titulo
                    break
            else:
                if pub_id not in seen:
                    seen.add(pub_id)
                    rows.append(
                        {
                            "pub_id": pub_id,
                            "titulo": titulo[:500],
                            "fecha": _parse_fecha_dmy(fecha_raw),
                            "url": f"{self.sede_base}/opensiac/informacionpublica/infopublica_ver.action?id={pub_id}",
                            "blob": titulo,
                            "origen": origen,
                            "edictos": edictos,
                        }
                    )
        return rows

    def _enrich_publication(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            html = self._fetch(row["url"])
        except urllib.error.URLError:
            return row
        fields: dict[str, str] = {}
        for m in RE_DETAIL_FIELD.finditer(html):
            key = _strip_html(m.group(1)).lower()
            val = _strip_html(m.group(2))
            fields[key] = val
        titulo = fields.get("título") or fields.get("titulo") or row.get("titulo")
        fecha = _parse_fecha_dmy(fields.get("fecha publicación", "")) or row.get("fecha")
        pdfs: list[str] = []
        for m in RE_PDF_LINK.finditer(html):
            pdfs.append(self._abs_sede(m.group(1)))
        blob = titulo or row.get("blob", "")
        return {
            **row,
            "titulo": (titulo or row.get("titulo", ""))[:500],
            "fecha": fecha,
            "blob": blob[:1000],
            "pdf_url": pdfs[0] if pdfs else None,
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        def add_rows(rows: list[dict[str, Any]], origen: str) -> None:
            for row in rows:
                pid = row["pub_id"]
                row["origen"] = origen
                if pid in merged:
                    prev = merged[pid]
                    for k, v in row.items():
                        if v and (k not in prev or not prev[k]):
                            prev[k] = v
                else:
                    merged[pid] = dict(row)

        index_ok = False
        try:
            index_html = self._fetch(TABLON_INDEX, timeout=25)
            add_rows(self._parse_listing_html(index_html, origen="tablon_index"), "tablon_index")
            index_ok = True
        except urllib.error.URLError:
            pass

        if index_ok:
            add_rows(
                self._search_publications(
                    edictos="OTROS",
                    descripcion_tipo="Ayuntamiento de Paterna",
                    referencia="OTROS",
                    todos=True,
                ),
                "tablon_todos",
            )
            for term in self.search_terms[:6]:
                add_rows(
                    self._search_publications(
                        edictos="OTROS",
                        descripcion_tipo="Ayuntamiento de Paterna",
                        referencia="OTROS",
                        descripcion=term,
                    ),
                    f"tablon_busqueda_{term.lower().replace(' ', '_')}",
                )

        return list(merged.values())

    def _wfs_page_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _parse_wfs_member(self, member: ET.Element, *, layer: str) -> dict[str, Any] | None:
        feat = None
        for tag in (f"{{{_GML_NS['ms']}}}{layer}", f"{{{_GML_NS['ms']}}}InventarioSuSuz"):
            feat = member.find(tag)
            if feat is not None:
                break
        if feat is None:
            for child in member:
                if child.tag.endswith("InventarioSuSuz") or child.tag.endswith("Zonificacion"):
                    feat = child
                    break
        if feat is None:
            return None
        cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
        if cod != self.cod_ine_mun:
            return None
        fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
        pp = _strip_html(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
        ue = _strip_html(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
        denom = _strip_html(
            feat.findtext("ms:denominaci", default="", namespaces=_GML_NS)
            or feat.findtext("ms:denominaci_val", default="", namespaces=_GML_NS)
            or ""
        )
        clas = _strip_html(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"
        geom = _gml_feature_to_geojson(feat)
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob,
            "url": VISOR_GVA,
            "tipo": "sector SU/SUZ" if clas else "zonificación ICV",
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._wfs_page_url(self.icv_layer_su, 0)
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"),):
            start = self.icv_start
            empty_pages = 0
            while start <= self.icv_max_start:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=45)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                page_hits = 0
                for member in members:
                    rec = self._parse_wfs_member(member, layer=layer.split(".")[-1])
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                        page_hits += 1
                if page_hits == 0:
                    empty_pages += 1
                    if empty_pages >= 12:
                        break
                else:
                    empty_pages = 0
                start += 200
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in RE_SECTOR_TOKEN.finditer(rec.get("titulo") or ""):
                self._wfs_by_key[tok.group(1).lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        return best

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "blob", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", LICENCIA_OBRA_TRAMITE),
                "fecha_concesion": None,
                "tipo": "licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de obra — trámite telemático (OpenSIAC)",
                "url": LICENCIA_OBRA_TRAMITE,
                "source": "ayuntamiento",
                "nota": "Declaración responsable / licencia urbanística (tramite 324)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", LICENCIA_USOS_TRAMITE),
                "fecha_concesion": None,
                "tipo": "licencias de usos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de usos — trámite telemático (OpenSIAC)",
                "url": LICENCIA_USOS_TRAMITE,
                "source": "ayuntamiento",
                "nota": "Cambios de uso / actividad (tramite 293)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", TRAMITES_CATALOGO),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de servicios — sede electrónica Paterna",
                "url": TRAMITES_CATALOGO,
                "source": "ayuntamiento",
                "nota": "Sin histórico público de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", TABLON_INDEX),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos (OpenSIAC)",
                "url": TABLON_INDEX,
                "source": "ayuntamiento",
                "nota": "Modificaciones PGOU, licencias ambientales, expropiaciones",
                "origen": "tablon_index",
            },
        ]

    def _is_urban(self, blob: str) -> bool:
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban(blob) or not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("url") or blob),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("origen") != "icv_wfs" and not self._is_urban(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and row.get("origen") != "icv_wfs":
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row.get("url") or blob),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "pub_id",
            "pdf_url",
            "pp",
            "ue",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

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
        rows = self._collect_licencia_info_pages()
        seen = {r["id"] for r in rows}
        for item in self._collect_tablon():
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon+tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_icv_wfs():
            proy = self._to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        for item in self._collect_tablon():
            proy = self._to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
