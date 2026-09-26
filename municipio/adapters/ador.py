from __future__ import annotations

import hashlib
import http.cookiejar
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

SEDE_BASE = "https://ador.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URBANISMO_URL = (
    f"{SEDE_BASE}/transparency/08b9f48a-afcd-4001-a9ae-af097842652b/"
)
TRANSPARENCIA_BASE = "https://transparencia.ador.es"
GVA_PLANEAMIENTO_BASE = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46002%20ADOR/"
)
MUNICIPIO = "Ador"
ID_PREFIX = "ador"
COD_INE_MUN = "46002"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "InventarioSuSuz"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmod|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|homolog|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|unidad de actuaci[oó]n|\bue\b|"
    r"normas subsidiarias|nnss|fase\s+[ivx]+|raconc|pinaret|ovo|monte corona)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(presupuestos participativos|selecci[oó]n de personal|nombramiento|"
    r"convocatoria.*empleo|subvenci[oó]n|modificaci[oó]n de cr[eé]ditos|"
    r"presupuest|empleo p[uú]blico|matrimonio)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ador\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSP_DOC = re.compile(
    r'href="(https://ador\.sedelectronica\.es/preview-document/[a-f0-9-]+)"[^>]*>([^<]+)',
    re.I,
)
RE_GVA_FOLDER = re.compile(
    r'href="((?:46002[^"]+/)|(?:[^"]+/46002[^"]*/))"[^>]*>([^<]+)</a>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GVA_YEAR = re.compile(r"\b(19|20)\d{2}\b")

GML_NS = {
    "gml": "http://www.opengis.net/gml/3.2",
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
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
    years = [int(x.group(0)) for x in RE_GVA_YEAR.finditer(text or "") if 1980 <= int(x.group(0)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "homolog" in b or "homopp" in b:
        return "homologación plan parcial"
    if "plan parcial" in b or re.search(r"\bpp\b", b):
        return "plan parcial"
    if "fase" in b and ("pgou" in b or "plan general" in b):
        return "PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "unidad de actuaci" in b or re.search(r"\bue\b", b):
        return "unidad de actuación"
    if "sector" in b:
        return "sector urbanizable"
    if "modificaci" in b:
        return "modificación planeamiento"
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


def _parse_gml_feature(member: ET.Element) -> dict[str, Any] | None:
    feat = member[0]
    props: dict[str, str | None] = {}
    geom: dict[str, Any] | None = None
    for child in feat:
        tag = child.tag.split("}")[-1]
        if tag == "msGeometry":
            pos = child.find(".//gml:posList", GML_NS)
            if pos is not None and pos.text:
                geom = _gml_poslist_to_geojson(pos.text)
            continue
        if tag == "boundedBy":
            continue
        props[tag] = (child.text or "").strip() or None
    if props.get("cod_ine_mun") != COD_INE_MUN:
        return None
    if (props.get("pp") or "").lower() == "example":
        return None
    return {"props": props, "geom": geom}


class AdorAyuntamientoAdapter(AyuntamientoAdapter):
    """DigitalValue transparencia + sede espublico gestiona + GVA planeamiento + ICV WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(
            self.config.get("transparency_urbanismo_url") or TRANSPARENCY_URBANISMO_URL
        )
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.gva_base = str(self.config.get("gva_planeamiento_base") or GVA_PLANEAMIENTO_BASE)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self.wfs_start_index = int(geom_cfg.get("wfs_start_index") or 500)
        self.wfs_page_size = int(geom_cfg.get("wfs_page_size") or 500)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ador/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ador/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = self.wfs_start_index
        empty_pages = 0
        while start < self.wfs_start_index + 2000 and empty_pages < 2:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.icv_type_name,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": str(self.wfs_page_size),
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.icv_wfs_url}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                empty_pages += 1
                start += self.wfs_page_size
                continue
            ador_in_page = 0
            for member in members:
                parsed = _parse_gml_feature(member)
                if parsed:
                    rows.append(parsed)
                    ador_in_page += 1
            if ador_in_page == 0 and rows:
                break
            start += len(members)
            if len(members) < self.wfs_page_size:
                break

        self._wfs_cache = rows
        return rows

    def _wfs_query_url(self, ambito_id: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.icv_type_name,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "1",
                "STARTINDEX": str(self.wfs_start_index),
            }
        )
        return f"{self.icv_wfs_url}?{params}#id={ambito_id}"

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_url = "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
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
            key = f"icv:{props.get('id')}:{pp}:{ue}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{pp} {ue} {clas}"),
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = self._wfs_query_url(str(props.get("id") or ""))
                rec["coord_source"] = "portal_geometry_centroid"
            rows.append(rec)
        return rows

    def _collect_transparency_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSP_DOC.finditer(html):
            url = m.group(1)
            label = _strip_html(m.group(2))
            if not label or url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": f"Planeamiento urbanístico — {label}"[:500],
                    "fecha": _fecha_from_blob(label),
                    "url": url,
                    "blob": label,
                    "origen": "sede_transparencia",
                }
            )
        return rows

    def _collect_gva_folders(self, index_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(index_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_GVA_FOLDER.finditer(html):
            href = unescape(m.group(1))
            name = _strip_html(m.group(2)).strip("/")
            if not name or name in seen or name.startswith("?"):
                continue
            seen.add(name)
            url = urllib.parse.urljoin(index_url, href)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name),
                    "url": url,
                    "blob": name,
                    "origen": origen,
                }
            )
        return rows

    def _collect_gva_planeamiento(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(
            self._collect_gva_folders(
                urllib.parse.urljoin(self.gva_base, "1%20P.%20GENERAL/"),
                "gva_pg",
            )
        )
        rows.extend(
            self._collect_gva_folders(
                urllib.parse.urljoin(self.gva_base, "2%20P.%20DIFERIDO/"),
                "gva_pd",
            )
        )
        rows.append(
            {
                "titulo": "Repositorio planeamiento urbanístico GVA — Ador",
                "fecha": None,
                "url": self.gva_base,
                "blob": "planeamiento GVA 46002 ADOR",
                "origen": "gva_indice",
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
            if not documento:
                continue
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            fecha = _parse_fecha_dmy(cells.get("class_startDate", "")) or _parse_fecha_dmy(
                cells.get("class_endDate", "")
            )
            link_m = RE_PREVIEW_LINK.search(row_html)
            url = link_m.group(1) if link_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            blob = f"{documento} {expediente} {procedimiento} {categoria}"
            rows.append(
                {
                    "titulo": documento[:500],
                    "fecha": fecha,
                    "url": url,
                    "expediente": expediente or None,
                    "procedimiento": procedimiento or None,
                    "categoria": categoria or None,
                    "blob": blob,
                    "origen": "tablon",
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(
            blob
        ):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "obra", "información pública")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _raw_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        blob = row.get("blob") or titulo
        key = row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for field in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if row.get(field) is not None:
                rec[field] = row[field]
        return rec

    def _collect_proyectos_raw(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(row: dict[str, Any]) -> None:
            key = row.get("id") or row.get("url") or row.get("titulo") or ""
            if key in seen:
                return
            seen.add(key)
            rows.append(row)

        for rec in self._collect_icv_proyectos():
            add(rec)
        for raw in self._collect_transparency_docs():
            if RE_PROYECTO.search(raw.get("blob") or raw.get("titulo") or ""):
                add(self._raw_to_proyecto(raw))
            else:
                add(self._raw_to_proyecto(raw))
        for raw in self._collect_gva_planeamiento():
            add(self._raw_to_proyecto(raw))
        for raw in self._collect_board():
            if self._board_is_urban(raw) and RE_PROYECTO.search(raw.get("blob") or ""):
                add(self._raw_to_proyecto(raw))
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones publicadas en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.transparencia_base}/es/transparencia/planejament-urbanistic"),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — planeamiento urbanístico",
                "url": f"{self.transparencia_base}/es/transparencia/planejament-urbanistic",
                "source": "ayuntamiento",
                "nota": "DigitalValue transparencia; enlaces a sede y GVA",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _read_state(self, state_path: Path) -> dict[str, Any]:
        if not state_path.is_file():
            return {}
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_state(self, state_path: Path, state: dict[str, Any]) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = list(self._collect_licencia_info_pages())
        for board_row in self._collect_board():
            lic = self._board_to_licencia(board_row)
            if lic:
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "sede_transparencia",
            "info_pages": sum(1 for r in rows if r.get("origen") != "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_licencias(out_jsonl)
        self._write_state(state_path, {"last_rows": result.get("rows", 0)})
        return result

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos_raw()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "sede_gva_icv",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "gva": sum(1 for r in rows if str(r.get("origen", "")).startswith("gva")),
            "sede_transparencia": sum(1 for r in rows if r.get("origen") == "sede_transparencia"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        self._write_state(state_path, {"last_rows": result.get("rows", 0)})
        return result
