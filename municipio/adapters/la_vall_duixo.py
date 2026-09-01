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

WEB_BASE = "https://www.lavallduixo.es"
SEDE_BASE = "https://sede.lavallduixo.es"
MUNICIPIO = "La Vall d'Uixó"
ID_PREFIX = "la-vall-duixo"
INE_MUNICIPIO = "12126"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"

URBANISMO_KEYWORD = "PTS_PC_004"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/planeamiento-urbanistico",
    f"{WEB_BASE}/es/exposicion-al-publico",
    f"{WEB_BASE}/es/plan-general-de-ordenacion-urbana",
    f"{WEB_BASE}/es/plan-especial-de-san-jose",
    f"{WEB_BASE}/es/plan-parcial-sector-1-c",
    f"{WEB_BASE}/es/plan-parcial-area-6",
    f"{WEB_BASE}/es/plan-parcial-area-7",
    f"{WEB_BASE}/es/plan-parcial-area-8",
    f"{WEB_BASE}/es/plan-parcial-area-9a",
    f"{WEB_BASE}/es/plan-parcial-area-10",
    f"{WEB_BASE}/es/plan-parcial-area-11",
    f"{WEB_BASE}/es/plan-parcial-sector-12",
    f"{WEB_BASE}/es/plan-parcial-sector-2-carmaday",
    f"{WEB_BASE}/es/plan-parcial-sector-4-belcaire",
    f"{WEB_BASE}/es/plan-parcial-reclasificacion-sumet",
    f"{WEB_BASE}/es/plan-parcial-reclasificacion-la-mezquita",
    f"{WEB_BASE}/es/pmus",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|primera ocupaci[oó]n|"
    r"certificado.*licencia|obra mayor|obra menor|transmisi[oó]n licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pmus|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto de (?:urbaniz|actuaci)|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|programa de actuaci|"
    r"unidad de (?:ejecuci[oó]n|actuaci)|ue\s*\d|sector\s*\d|plan parcial)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(subvenci[oó]n|bolsa de|proceso selectivo|oposici[oó]n|"
    r"cobranza del iae|plantilla respuestas examen|huertos urbanos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/files/(\d{4})-(\d{2})/")
RE_DRUPAL_PDF = re.compile(r'href="(/sites/L01121264/files/[^"]+\.(?:pdf|zip))"', re.I)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector|ue|area|área|p\.?\s*|plan parcial)\s*([A-Z0-9][\w\-\s]{0,12})\b",
)

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = re.findall(r"\b((?:19|20)\d{2})\b", Path(urllib.parse.unquote(url)).name)
    valid = [int(y) for y in years if 1980 <= int(y) <= 2035]
    if valid:
        return f"{max(valid)}-01-01"
    return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.(pdf|zip)$", "", name, flags=re.I)
    name = name.replace("%20", " ").replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name[:500] if name else url


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(section: str, title: str) -> str:
    blob = f"{section} {title}".lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "pmus" in blob:
        return "PMUS"
    if "pgou" in blob or "ordenaci" in blob or "planeam" in blob:
        return "planeamiento"
    if "modificaci" in blob:
        return "modificación planeamiento"
    return section or "urbanismo"


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


class LaVallDuixoAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal web (planeamiento PDFs) + sede STA (tablón + catálogo) + ICV WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_municipio = str(geom_cfg.get("ine_municipio") or INE_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-vall-duixo/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.lavallduixo.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-vall-duixo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, expte, url

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            dboid = str(item.get("dboid") or code)
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
            )
            rows.append({"name": name, "code": code, "url": url})
        return rows

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = 0
        while start < 20_000:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.wfs_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "200",
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.wfs_base}/ows?{params}"
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                break
            for member in members:
                parsed = _parse_gml_feature(member)
                if parsed:
                    rows.append(parsed)
            start += len(members)
            if len(members) < 200:
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
                "CQL_FILTER": f"id='{ambito_id.replace(chr(39), chr(39)+chr(39))}'",
            }
        )
        return f"{self.wfs_base}/ows?{params}"

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
                "tipo": _proyecto_tipo("icv_wfs", f"{pp} {ue} {clas}"),
                "url": (
                    "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                    f"#municipio={urllib.parse.quote(MUNICIPIO)}"
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

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            page_title = unescape(re.sub(r"<[^>]+>", " ", h1_m.group(1))).strip() if h1_m else page_url
            page_title = re.sub(r"\s+", " ", page_title)
            for m in RE_DRUPAL_PDF.finditer(html):
                href = m.group(1)
                doc_url = self._abs_web(href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                name = _title_from_url(doc_url)
                titulo = f"{page_title} — {name}" if name.lower() not in page_title.lower() else name
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_url(doc_url),
                        "url": doc_url,
                        "page_url": page_url,
                        "blob": f"{titulo} {page_url}",
                        "origen": "drupal_planeamiento",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón licencias y edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica STA",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios publicados en sede TAO/STA",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — Urbanismo y Vivienda",
                "url": CATALOGO_URL,
                "source": "ayuntamiento",
                "nota": "Licencias de obra, comunicaciones previas y ocupaciones vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/es/planeamiento-urbanistico"),
                "fecha_concesion": None,
                "tipo": "planeamiento urbanístico (web)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Planeamiento urbanístico — Ayuntamiento",
                "url": f"{self.web_base}/es/planeamiento-urbanistico",
                "source": "ayuntamiento",
                "nota": "PGOU, planes parciales y exposición al público",
                "origen": "web_tramite",
            },
        ]

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if not RE_LICENCIA.search(blob):
            return None
        key = expte or url
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo",
        }

    def _tramite_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
            return None
        if not RE_PROYECTO.search(name):
            return None
        rec = {
            "id": _stable_id("proy", item["code"]),
            "municipio": MUNICIPIO,
            "titulo": name[:500],
            "fecha": None,
            "tipo": _proyecto_tipo("trámite", name),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "catalogo",
        }
        self._attach_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_PROY.search(blob):
            return None
        is_urbanismo = "URBANISMO" in remitente.upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        key = expte or url
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(remitente, title),
            "url": url,
            "expte": expte or None,
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo("drupal", row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "drupal_planeamiento",
        }
        self._attach_geometry(rec)
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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
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

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_planeamiento"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
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
