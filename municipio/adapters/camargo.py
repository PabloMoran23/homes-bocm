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

SEDE_BASE = "https://sede.aytocamargo.es"
WEB_BASE = "https://www.aytocamargo.es"
MUNICIPIO = "Camargo"
ID_PREFIX = "camargo"
COD_INE = "39016"

INFO_PUBLICA = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica.action"
SEARCH_URL = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica_search.action"
TRAMITES_CATALOGO = f"{SEDE_BASE}/opensiac/informacionpublica/tramites_enter.action"
TABLON_CUSTOM = f"{SEDE_BASE}/opensiac/custom.action"
URBANISMO_WEB = f"{WEB_BASE}/urbanismo-medio-ambiente-servicios/urbanismo"
PLANOS_ORDENACION = f"{WEB_BASE}/urbanismo-medio-ambiente-servicios/urbanismo/planos-ordenacion"
WFS_BASE = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
WFS_NS = WFS_BASE

SEARCH_TERMS = [
    "URBAN",
    "PGOU",
    "PLANEAM",
    "LICENC",
    "CONVENIO",
    "MODIFIC",
    "INFORMACION PUBLICA",
    "UNIDAD DE ACTUACION",
]

RE_LICENCIA = re.compile(
    r"(?i)(?:licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"legalizaci[oó]n|apertura.*local|actividad econ[oó]mica|lic/)",
)
RE_PROYECTO = re.compile(
    r"(?i)(?:planeam|pgou|convenio urban|agenda urbana|unidad de actuaci|"
    r"informaci[oó]n p[uú]blica|urbanismo|lic/\d|valle real|reparcel|expropiaci|"
    r"estudio de detalle|plan (?:parcial|especial|general)|"
    r"modificaci[oó]n.*(?:pgou|planeam|urban)|sector(?:izaci)?|"
    r"ordenanza municipal reguladora de la identificaci)",
)
RE_PROYECTO_EXCLUDE = re.compile(
    r"(?i)(presupuesto|ordenanza fiscal|tasa por|permiso de conducci|"
    r"inmatriculaci|bolera|comida a domicilio|servicios deportivos|"
    r"cruce a distinto nivel|transporte urbano|auto.?tax|"
    r"proyecto de construcci[oó]n de nuevo cruce|dominio para inmatricul)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|bolsa de trabajo|jurado|censo electoral|"
    r"licencias de auto.?tax|transporte urbano de viajeros|mercadillo|"
    r"hogueras de san juan|banda de m[uú]sica|monitor cultural|"
    r"convenio marco.*juntas vecinales|inmuebles culturales)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_INDEX_ROW = re.compile(
    r'listaPublicacionesDescripcion">(.*?)</td>\s*<td[^>]*>\s*(\d{2}/\d{2}/\d{4}).*?'
    r"infopublica_ver\.action[^?]*\?id=(\d+)",
    re.S | re.I,
)
RE_DETAIL_FIELD = re.compile(
    r'<td class="Etiqueta">([^<]+)</td>\s*<td class="Descripcion">(.*?)</td>',
    re.I | re.S,
)
RE_PDF_LINK = re.compile(
    r'href="(/opensiac/informacionpublica/infopublica_descargar\.action[^"]+)"',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"A\d{2}\.\d{2}|"
    r"UA[-\s.]?\d+|"
    r"UNIDAD DE ACTUACI[OÓ]N\s+[A-Z0-9.]+|"
    r"SECTOR\s+[A-Z0-9.-]{1,12}|"
    r"SUNP-\d+|SUP-\d+|SUC-\d+"
    r")\b",
)
GML_NS = "http://www.opengis.net/gml"


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


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = re.sub(r"^UNIDAD DE ACTUACI[OÓ]N\s+", "A", code)
    return code.strip()


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio urban" in n:
        return "convenio urbanístico de planeamiento"
    if "agenda urbana" in n:
        return "agenda urbana"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "unidad de actuaci" in n:
        return "unidad de actuación"
    if "lic/" in n:
        return "expediente urbanístico"
    if "sector" in n:
        return "sector urbanístico"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        ring.append([nums[i], nums[i + 1]])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    geoms: list[dict[str, Any]] = []
    for pos in feat.findall(f".//{{{GML_NS}}}posList"):
        if pos.text:
            geom = _gml_poslist_to_polygon(pos.text.strip())
            if geom:
                geoms.append(geom)
    if not geoms:
        return None
    if len(geoms) == 1:
        return geoms[0]
    return {"type": "MultiPolygon", "coordinates": [g["coordinates"] for g in geoms]}


class CamargoAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenSIAC sede.aytocamargo.es + web PGOU + SIUCAN WFS Cantabria (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.search_terms = [str(t) for t in (self.config.get("search_terms") or SEARCH_TERMS)]
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_sector_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-camargo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            charset = resp.headers.get_content_charset() or "iso-8859-15"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href.replace("&amp;", "&")))

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
                    "url": f"{self.sede_base}/opensiac/informacionpublica/infopublica_ver.action?id={pub_id}",
                    "blob": titulo,
                    "origen": "tablon_opensiac",
                }
            )
        return rows

    def _search_publications(self, descripcion: str) -> list[dict[str, Any]]:
        params = {
            "edictos": "OTROS",
            "descripcionTipoTablon": "Ayuntamiento de Camargo",
            "referencia": "OTROS",
            "descripcionPublicacion": descripcion,
            "botonBuscar": "Buscar",
        }
        data = urllib.parse.urlencode(params).encode("iso-8859-15", errors="replace")
        try:
            html = self._fetch(SEARCH_URL, data=data)
        except urllib.error.URLError:
            return []
        return self._parse_infopublica_index(html)

    def _enrich_publication(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            html = self._fetch(row["url"])
        except urllib.error.URLError:
            return row
        fields: dict[str, str] = {}
        for m in RE_DETAIL_FIELD.finditer(html):
            key = _strip_html(m.group(1)).lower()
            fields[key] = _strip_html(m.group(2))
        titulo = fields.get("título") or fields.get("titulo") or row.get("titulo")
        fecha = _parse_fecha_dmy(fields.get("fecha publicación", "")) or row.get("fecha")
        pdfs = [self._abs_sede(m.group(1)) for m in RE_PDF_LINK.finditer(html)]
        blob = " ".join(filter(None, [titulo, " ".join(pdfs)]))
        return {
            **row,
            "titulo": (titulo or row.get("titulo", ""))[:500],
            "fecha": fecha,
            "blob": blob[:1200],
            "pdf_url": pdfs[0] if pdfs else None,
            "pdfs": pdfs,
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(INFO_PUBLICA)
            for row in self._parse_infopublica_index(html):
                merged[row["pub_id"]] = row
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for row in self._search_publications(term):
                pid = row["pub_id"]
                if pid in merged:
                    prev = merged[pid]
                    for k, v in row.items():
                        if v and not prev.get(k):
                            prev[k] = v
                else:
                    merged[pid] = row
        return list(merged.values())

    def _wfs_query_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "1.1.0",
                "request": "GetFeature",
                "typeName": "Urbanismo:Sectores",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "maxFeatures": "5000",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        url = self._wfs_query_url()
        try:
            raw = self._fetch(url)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            self._wfs_cache = rows
            return rows
        for feat in root.findall(f".//{{{WFS_NS}}}Sectores"):
            ine = feat.findtext(f"{{{WFS_NS}}}Código_INE") or ""
            mun = feat.findtext(f"{{{WFS_NS}}}Denominación_Municipio") or ""
            if ine != self.cod_ine and mun != MUNICIPIO:
                continue
            sector_code = _strip_html(feat.findtext(f"{{{WFS_NS}}}Código_Sector") or "")
            sector_name = _strip_html(feat.findtext(f"{{{WFS_NS}}}Denominación_Sector") or "")
            titulo = sector_name or sector_code or "Sector urbanístico"
            if sector_code and sector_code not in titulo:
                titulo = f"{sector_code} — {titulo}"
            geom = _gml_feature_to_geojson(feat)
            key = f"{sector_code}:{sector_name}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{key}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": "sector urbanístico",
                "url": URBANISMO_WEB,
                "source": "ayuntamiento",
                "origen": "siucan_wfs",
                "sector_code": sector_code or None,
                "sector_name": sector_name or None,
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _build_wfs_sector_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_sector_index is not None:
            return self._wfs_sector_index
        index: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wfs_proyectos():
            for token in (
                str(rec.get("sector_code") or ""),
                str(rec.get("sector_name") or ""),
                str(rec.get("titulo") or ""),
            ):
                for code in _sector_codes_from_text(token):
                    index.setdefault(code, rec)
                norm = _normalize_sector_code(token)
                if norm:
                    index.setdefault(norm, rec)
        self._wfs_sector_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "url", "pdf_url"))
        index = self._build_wfs_sector_index()
        for code in _sector_codes_from_text(blob):
            hit = index.get(code) or index.get(_normalize_sector_code(code))
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_crs",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "sector_code",
                "sector_name",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _collect_pgou_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Urbanismo — servicio municipal (licencias y calificación)",
                "fecha": None,
                "url": URBANISMO_WEB,
                "blob": "PGOU Camargo urbanismo licencias construcción calificación suelo",
                "origen": "web_urbanismo",
                "tipo": "PGOU",
            },
            {
                "titulo": "PGOU Camargo — planos de ordenación (clasificación y calificación del suelo)",
                "fecha": None,
                "url": PLANOS_ORDENACION,
                "blob": "PGOU planos ordenación clasificación calificación suelo Camargo",
                "origen": "web_pgou_planos",
                "tipo": "PGOU",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TRAMITES_CATALOGO),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — Urbanismo, territorio y vivienda (OpenSIAC)",
                "url": TRAMITES_CATALOGO,
                "source": "ayuntamiento",
                "nota": "Licencias de obra, actividad y apertura; sin histórico público de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", INFO_PUBLICA),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — información pública (OpenSIAC)",
                "url": INFO_PUBLICA,
                "source": "ayuntamiento",
                "nota": "Grupo Urbanismo con convenios y actuaciones puntuales",
                "origen": "tablon_index",
            },
            {
                "id": _stable_id("lic", TABLON_CUSTOM),
                "fecha_concesion": None,
                "tipo": "tablones de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablones de anuncios (sede electrónica)",
                "url": TABLON_CUSTOM,
                "source": "ayuntamiento",
                "origen": "tablon_custom",
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
        key = row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _to_proyecto(self, row: dict[str, Any], *, enrich: bool = False) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_PROYECTO_EXCLUDE.search(blob):
            return None
        if not self._is_urban(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if enrich and row.get("pub_id"):
            row = self._enrich_publication(row)
            blob = row.get("blob") or blob
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("pub_id"):
            rec["pub_id"] = row["pub_id"]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._to_proyecto(item, enrich=True))
        for seed in self._collect_pgou_seeds():
            add(self._to_proyecto(seed))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "siucan_wfs": sum(1 for r in rows if r.get("origen") == "siucan_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_opensiac"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
