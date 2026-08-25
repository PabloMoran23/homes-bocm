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
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://betxi.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
WEB_BASE = "https://betxi.es"
URBANISMO_URL = f"{WEB_BASE}/viure-a-betxi/urbanisme-2/"
TRAMITES_URB_URL = f"{WEB_BASE}/lajuntament/administracio/tramits/tramits-obres-i-urbanisme/"
CITIZEN_URB_URL = f"{SEDE_BASE}/citizen-service/92426f7b-213a-4925-ace5-f4145545f963"
MUNICIPIO = "Betxí"
ID_PREFIX = "betxi"
COD_INE_MUN = "12021"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_INVENTARIO = "ms:InventarioSuSuz"
ICV_ZONIFICACION = "ms:Planeamiento.Zonificacion"
VISOR_GVA_URL = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    TRAMITES_URB_URL,
    f"{WEB_BASE}/lajuntament/administracio/tramits/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:major|menor)|minimizaci[oó]n de impacto territorial|lmit|estudio de integraci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de integraci[oó]n)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|homologaci[oó]n|ordenanza|e[oó]lic|reforma interior|mobilitat|pmus|eate)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"modificaci[oó]n de cr[eé]ditos|cr[eé]ditos n|suplemento de cr[eé]dito|presupuest|"
    r"subvenci[oó]n|empleo p[uú]blico|admitidos|listado provisional)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://betxi\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r'\.pdf', re.I)


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


def _fecha_from_expediente(expediente: str) -> str | None:
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 8:
        try:
            y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
            if 1980 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(expediente or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_fecha_iso(text: str) -> str | None:
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "normas subsidiarias" in b or "nnss" in b:
        return "normas subsidiarias"
    if "plan parcial" in b or re.search(r"\bpp\b|sector", b):
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "reforma interior" in b or "pri " in b:
        return "reforma interior"
    if "mobilitat" in b or "pmus" in b:
        return "movilidad urbana"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "homologaci" in b:
        return "homologación planeamiento"
    if re.search(r"\bsu[z]?\b", b):
        return "sector urbanizable"
    return "planeamiento"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
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


class BetxiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress betxi.es + sede espublico gestiona + ICV WFS InventarioSuSuz/Zonificacion (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tramites_urb_url = str(self.config.get("tramites_urb_url") or TRAMITES_URB_URL)
        self.citizen_urb_url = str(self.config.get("citizen_urb_url") or CITIZEN_URB_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_inventario_cache: list[dict[str, Any]] | None = None
        self._wfs_zonificacion_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-betxi/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-betxi/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _wfs_geojson_url(self, type_name: str, count: int = 5000) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": type_name,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": str(count),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

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

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_HREF.findall(html):
                if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                full = urljoin(page_url, href)
                if "betxi.es" not in full and "betxi.sedelectronica.es" not in full:
                    continue
                if full in seen:
                    continue
                if not (
                    "/urbanisme" in full.lower()
                    or RE_PDF.search(full)
                    or any(k in full.lower() for k in ("pmus", "nnss", "planeam", "mobilitat"))
                ):
                    continue
                seen.add(full)
                name = _clean_title(unquote(Path(full).name))
                if not name or len(name) < 3:
                    name = full
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(name) or _fecha_from_expediente(name),
                        "url": full,
                        "page_url": page_url,
                        "origen": "web_urbanismo",
                    }
                )
        return rows

    def _inventario_to_proyecto(self, feat: dict[str, Any], wfs_url: str) -> dict[str, Any] | None:
        props = feat.get("properties") or {}
        if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
            return None
        pp = str(props.get("pp") or "").strip()
        ue = str(props.get("ue") or "").strip()
        clas = str(props.get("clasificacion") or "").strip()
        titulo = _clean_title(f"{clas} {pp} {ue}".strip())
        if not titulo:
            return None
        key = str(props.get("id") or f"{pp}:{ue}")
        fecha = _parse_fecha_iso(str(props.get("f_aprob") or "")) or _parse_fecha_iso(
            str(props.get("f_public") or "")
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"inventario:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {clas}"),
            "url": VISOR_GVA_URL,
            "source": "ayuntamiento",
            "origen": "icv_inventario",
            "clasificacion": clas or None,
            "uso": props.get("uso"),
        }
        geom = feat.get("geometry")
        if isinstance(geom, dict) and geom.get("type"):
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = wfs_url
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
        return rec

    def _collect_wfs_inventario(self) -> list[dict[str, Any]]:
        if self._wfs_inventario_cache is not None:
            return self._wfs_inventario_cache
        url = self._wfs_geojson_url(ICV_INVENTARIO)
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_inventario_cache = []
            return []
        rows: list[dict[str, Any]] = []
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            rec = self._inventario_to_proyecto(feat, url)
            if rec:
                rows.append(rec)
        self._wfs_inventario_cache = rows
        return rows

    def _collect_wfs_zonificacion(self) -> list[dict[str, Any]]:
        if self._wfs_zonificacion_cache is not None:
            return self._wfs_zonificacion_cache
        url = self._wfs_geojson_url(ICV_ZONIFICACION)
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_zonificacion_cache = []
            return []

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                continue
            key = (str(props.get("expediente") or ""), str(props.get("denominaci") or ""))
            grouped.setdefault(key, []).append(feat)

        rows: list[dict[str, Any]] = []
        for (expediente, denominaci), feats in grouped.items():
            titulo = _clean_title(denominaci or expediente)
            if not titulo:
                continue
            merged = _merge_geometries(feats)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"zonificacion:{expediente}:{denominaci}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_expediente(expediente),
                "tipo": _proyecto_tipo(titulo),
                "url": VISOR_GVA_URL,
                "source": "ayuntamiento",
                "origen": "icv_zonificacion",
                "expte": expediente or None,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        self._wfs_zonificacion_cache = rows
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en sede espublico",
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
                "nota": "Licencias, DR y comunicaciones previas vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.tramites_urb_url),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo y obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — obras y urbanismo (formularios web)",
                "url": self.tramites_urb_url,
                "source": "ayuntamiento",
                "nota": "Modelos licencia obra menor, DR y primera ocupación",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.citizen_urb_url),
                "fecha_concesion": None,
                "tipo": "servicio ciudadano urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Obres i urbanisme — sede electrónica",
                "url": self.citizen_urb_url,
                "source": "ayuntamiento",
                "nota": "Enlace ciudadano sede espublico",
                "origen": "sede_tramite",
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
                "nota": "Requiere identificación; sin listado histórico público",
                "origen": "sede_tramite",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.urbanismo_url),
                "municipio": MUNICIPIO,
                "titulo": "Urbanisme — instrumentos de planeamiento (web municipal)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
                "nota": "NNSS, modificaciones, PMUS, planeamiento en tramitación",
            },
            {
                "id": _stable_id("proy", f"{self.sede_base}/transparency"),
                "municipio": MUNICIPIO,
                "titulo": "Portal de transparencia — urbanismo",
                "fecha": None,
                "tipo": "planeamiento",
                "url": f"{self.sede_base}/transparency",
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("proy", VISOR_GVA_URL),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": VISOR_GVA_URL,
                "source": "ayuntamiento",
                "origen": "datos_abiertos",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llic")):
            return True
        if "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "licencias urban" not in (row.get("procedimiento") or "").lower():
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
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower():
                return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "normativa" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento|normas subsidiarias|homologaci[oó]n", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)ordenanza|reglamento", blob):
            tipo = "normativa"

        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('url', '')}"
        if not RE_PROYECTO.search(blob) and not RE_PDF.search(row.get("url", "")):
            return None
        key = row.get("url") or titulo
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for rec in self._collect_wfs_inventario():
            add(rec)
        for rec in self._collect_wfs_zonificacion():
            add(rec)
        for item in self._collect_web_proyectos():
            add(self._web_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv_inventario": sum(1 for r in rows if r.get("origen") == "icv_inventario"),
            "icv_zonificacion": sum(1 for r in rows if r.get("origen") == "icv_zonificacion"),
            "web": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
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
