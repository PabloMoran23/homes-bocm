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
from urllib.parse import unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.almoradi.es"
SEDE_BASE = "https://almoradi.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Almoradí"
ID_PREFIX = "almoradi"
INE_MUN = "03009"
# Bbox aproximado término municipal (WGS84, lat/lon) — filtra SuSuz ICV mal georreferenciados.
MUN_MIN_LAT, MUN_MAX_LAT = 38.02, 38.20
MUN_MIN_LON, MUN_MAX_LON = -0.88, -0.65

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/areas/urbanismo/",
    f"{WEB_BASE}/areas/urbanismo/plan-general-estructural/",
    f"{WEB_BASE}/areas/urbanismo/normas-subsidiarias-de-planeamiento-municipal/",
    f"{WEB_BASE}/areas/urbanismo/instancias-urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|instancia.?solicitud|"
    r"cambio de uso|compatibilidad|enterramiento|numero de polic[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estructural)|pge|pgou|"
    r"normas subsidiarias|informaci[oó]n p[uú]blica|expedient|expropi|"
    r"unidad de actuaci[oó]n|\bua[\s\-]?\d|estudio (?:ac[uú]stico|ambiental)|"
    r"memoria|catalogo|nnuu|modificaci[oó]n)",
)
RE_BOARD_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|padr[oó]n (?:municipal|fiscal)|empleo p[uú]blico|"
    r"subvenci[oó]n|matrimonio|mercadillo|boda civil|pleno|bolsa de)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://almoradi\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="(https://www\.almoradi\.es/wp-content/uploads/[^"]+\.(?:pdf|PDF))"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan general estructural" in b or "pge" in b:
        return "plan general estructural"
    if "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "plan especial" in b:
        return "plan especial"
    if "informaci" in b or "exposici" in b:
        return "información pública"
    if "expropi" in b:
        return "expropiación"
    if re.search(r"\bua[\s\-]?\d", b):
        return "unidad de actuación"
    if "licencia" in b:
        return "licencia publicada"
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


class AlmoradiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress almoradi.es + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        bbox = geom_cfg.get("bbox") or {}
        self.mun_min_lat = float(bbox.get("min_lat", MUN_MIN_LAT))
        self.mun_max_lat = float(bbox.get("max_lat", MUN_MAX_LAT))
        self.mun_min_lon = float(bbox.get("min_lon", MUN_MIN_LON))
        self.mun_max_lon = float(bbox.get("max_lon", MUN_MAX_LON))
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almoradi/1.0")},
        )
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        with opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almoradi/1.0")},
        )
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        with opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.wfs_base}?{params}"

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        max_index = int(self.config.get("wfs_max_startindex") or 16000)
        while start < max_index:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", GML_NS)
                if feat is None and member:
                    feat = member[0]
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=GML_NS)
                if cod != self.ine_mun:
                    continue
                props: dict[str, str | None] = {}
                for tag in ("id", "pp", "ue", "clasificacion", "f_aprob", "f_public", "noms_mun"):
                    props[tag] = feat.findtext(f"ms:{tag}", default="", namespaces=GML_NS) or None
                geom: dict[str, Any] | None = None
                poly = feat.find(".//gml:Polygon", GML_NS)
                if poly is not None:
                    pos = poly.find(".//gml:posList", GML_NS)
                    if pos is not None and pos.text:
                        geom = _gml_poslist_to_geojson(pos.text)
                rows.append({"props": props, "geom": geom})
            start += len(members)
            if len(members) < 200:
                break
        self._wfs_cache = rows
        return rows

    def _geom_in_municipio(self, geom: dict[str, Any] | None) -> bool:
        if not geom:
            return False
        centroid = geometry_centroid(geom)
        if not centroid:
            return False
        lat, lon = centroid
        return (
            self.mun_min_lat <= lat <= self.mun_max_lat
            and self.mun_min_lon <= lon <= self.mun_max_lon
        )

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
            if not titulo:
                continue
            fecha = props.get("f_aprob") or props.get("f_public")
            feat_id = str(props.get("id") or f"{pp}:{ue}")
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{feat_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{pp} {ue} {clas}"),
                "url": "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz",
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "sector": pp,
                "ue": ue,
            }
            if geom and self._geom_in_municipio(geom):
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_axis_order"] = "xy"
                rec["geometry_source"] = "portal_wfs_icv"
                rec["geometry_source_url"] = self._wfs_page_url(0)
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
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
            if page_url not in seen and RE_PROYECTO.search(page_title):
                seen.add(page_url)
                rows.append(
                    {
                        "titulo": page_title[:500],
                        "fecha": _fecha_from_blob(page_title),
                        "url": page_url,
                        "blob": page_title,
                        "origen": "web_pagina",
                    }
                )
            for m in RE_WP_PDF.finditer(html):
                doc_url = m.group(1)
                if doc_url in seen:
                    continue
                name = unquote(Path(doc_url).name).replace("-", " ").replace("_", " ")
                titulo = f"{page_title} — {name}"
                blob = titulo
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name),
                        "url": doc_url,
                        "pdf_url": doc_url,
                        "blob": blob,
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                }
            )
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            ue = str(wfs_rec.get("ue") or "").lower()
            if ue and ue in titulo:
                for key in (
                    "geom_geojson",
                    "geometry_crs",
                    "geometry_axis_order",
                    "geometry_source",
                    "geometry_source_url",
                    "coord_source",
                    "lat",
                    "lon",
                ):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
                return
            if titulo and len(titulo) > 8 and titulo in wfs_title:
                for key in (
                    "geom_geojson",
                    "geometry_crs",
                    "geometry_axis_order",
                    "geometry_source",
                    "geometry_source_url",
                    "coord_source",
                    "lat",
                    "lon",
                ):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_BOARD_SKIP.search(row.get("blob") or ""):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sede",
        }

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("blob") or row.get("titulo") or ""):
            return None
        if RE_PROYECTO.search(row.get("blob") or "") and not RE_LICENCIA.search(
            row.get("titulo") or ""
        ):
            return None
        key = row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "formulario / instancia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "nota": "Modelo descargable; no registro de concesiones en tablón",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_BOARD_SKIP.search(row.get("blob") or ""):
            return None
        if not RE_PROYECTO.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon_sede",
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_licencia(item))
        for item in self._collect_seed_docs():
            add(self._doc_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_wfs_proyectos():
            add(item)
        for item in self._collect_seed_docs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
