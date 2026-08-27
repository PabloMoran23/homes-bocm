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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://realdegandia.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://www.realdegandia.es"
URBANISMO_URL = f"{WEB_BASE}/es/pagina/urbanismo"
NORMAS_URL = f"{WEB_BASE}/es/pagina/normas-urbanisticas"
TRANSPARENCIA_URBANISTICA_URL = f"{WEB_BASE}/es/transparencia/informacion-urbanistica"
NORMAS_SUBSIDIARIAS_PDF = (
    f"{WEB_BASE}/sites/www.realdegandia.es/files/files/tramites/urbanismo/"
    "normas_urbanisticas_-_real_de_gandia.pdf"
)
MUNICIPIO = "El Real de Gandia"
ID_PREFIX = "el-real-de-gandia"
COD_INE_MUN = "46205"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    NORMAS_URL,
    TRANSPARENCIA_URBANISTICA_URL,
]

STATIC_WEB_PROYECTOS: list[tuple[str, str, str, str | None]] = [
    (
        "Normas subsidiarias de El Real de Gandia",
        "normativa",
        NORMAS_SUBSIDIARIAS_PDF,
        "1994-06-14",
    ),
    (
        "Normas urbanísticas del plan parcial Germanias",
        "plan parcial",
        NORMAS_URL,
        None,
    ),
    (
        "Normas urbanísticas del plan parcial Vernisa",
        "plan parcial",
        NORMAS_URL,
        None,
    ),
    (
        "Normas urbanísticas del plan parcial Novoperfil",
        "plan parcial",
        NORMAS_URL,
        None,
    ),
    (
        "Plan local de quemas — término municipal",
        "planificación forestal",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
    (
        "Plan de autoprotección ante emergencia — urbanización Monte-Real",
        "plan de emergencia",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
    (
        "Plan de autoprotección ante emergencia — urbanización Monte Rey",
        "plan de emergencia",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
    (
        "Pla Urbà d'Actuacions Municipals (PUAM)",
        "PUAM",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
    (
        "Plan local reducido de prevención de incendios forestales (PLPIF)",
        "plan forestal",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
    (
        "Trámite información pública plan parcial",
        "información pública",
        TRANSPARENCIA_URBANISTICA_URL,
        None,
    ),
]

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|minimizaci[oó]n de impacto territorial|lmit|estudio de integraci[oó]n|"
    r"modificaci[oó]n sustancial)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de integraci[oó]n)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|e[oó]lic|iate|font baixa)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|auxiliar administrativo|modificaci[oó]n de cr[eé]ditos|"
    r"cr[eé]ditos n|suplemento de cr[eé]dito|presupuest|subvenci[oó]n|empleo p[uú]blico|"
    r"matrimonio|delegaci[oó]n de funciones|bolsa de t[eé]cnico|becas a deportistas|"
    r"ayudas a entidades culturales)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://realdegandia\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.realdegandia\.es)?/sites/www\.realdegandia\.es/files/[^"]+\.pdf)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+)")


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry") if "geometry" in f else f.get("geom_geojson")
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


def _proyecto_tipo(denominaci: str) -> str:
    n = (denominaci or "").lower()
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "homologaci" in n:
        return "homologación planeamiento"
    return "planeamiento"


class ElRealDeGandiaAyuntamientoAdapter(AyuntamientoAdapter):
    """Adaptive Theme (realdegandia.es) + sede espublico gestiona + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.normas_url = str(self.config.get("normas_url") or NORMAS_URL)
        self.transparencia_urbanistica_url = str(
            self.config.get("transparencia_urbanistica_url") or TRANSPARENCIA_URBANISTICA_URL
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))
        self.web_fetch_timeout = int(self.config.get("web_fetch_timeout", 8))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
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
        self._icv_zones_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-real-de-gandia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_web(self, url: str) -> str | None:
        try:
            return self._fetch(url, timeout=self.web_fetch_timeout)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _collect_static_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for titulo, tipo, url, fecha in STATIC_WEB_PROYECTOS:
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url + titulo),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": tipo,
                "url": url,
                "source": "ayuntamiento",
                "origen": "web_estatico",
            }
            self._enrich_geometry(rec, licencia=False)
            rows.append(rec)
        return rows

    def _collect_web_crawl_proyectos(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []
        queue = list(self.seed_pages)
        visited: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            html = self._fetch_web(url)
            if not html:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = m.group(1)
                if pdf.startswith("/"):
                    pdf = f"{self.web_base}{pdf}"
                if pdf in seen_urls:
                    continue
                seen_urls.add(pdf)
                titulo = pdf.rsplit("/", 1)[-1].replace("_", " ").replace("-", " ")
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_expediente(pdf),
                    "tipo": _proyecto_tipo(titulo),
                    "url": pdf,
                    "source": "ayuntamiento",
                    "origen": "web_pdf",
                }
                self._enrich_geometry(rec, licencia=False)
                rows.append(rec)
        return rows

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-real-de-gandia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _collect_icv_zones(self) -> list[dict[str, Any]]:
        if self._icv_zones_cache is not None:
            return self._icv_zones_cache

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for start in self.icv_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.icv_type_name,
                    "outputFormat": "application/json; subtype=geojson",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.icv_wfs_url}?{params}"
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            batch = data.get("features") or []
            if not batch:
                break
            for feat in batch:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                    continue
                den = str(props.get("denominaci") or "").strip()
                exp = str(props.get("expediente") or "").strip()
                if not den:
                    continue
                grouped.setdefault((den, exp), []).append(feat)

        zones: list[dict[str, Any]] = []
        for (den, exp), feats in grouped.items():
            merged = _merge_geometries(feats)
            zones.append(
                {
                    "denominaci": den,
                    "expediente": exp,
                    "tipo": _proyecto_tipo(den),
                    "geom_geojson": merged,
                    "geometry_source_url": (
                        f"{self.icv_wfs_url}?service=WFS&request=GetFeature&"
                        f"typeName={self.icv_type_name}&cod_ine_mun={self.cod_ine_mun}"
                    ),
                }
            )

        self._icv_zones_cache = zones
        return zones

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        sector_m = RE_SECTOR.search(titulo or "")
        sector = sector_m.group(1).upper() if sector_m else None
        best: tuple[float, dict[str, Any]] | None = None

        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif sector and f"SECTOR {sector}" in den:
                score = 80.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if "PLAN GENERAL" in norm and "PLAN GENERAL" in den:
                score += 20.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)

        if best and best[0] >= 20:
            return best[1]
        return None

    def _zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        geom = zone.get("geom_geojson")
        if not geom:
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": zone.get("geometry_source_url") or self.icv_wfs_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any], *, licencia: bool = False) -> None:
        if record_geometry(rec):
            return
        if rec.get("origen") == "tablon" and licencia:
            if not re.search(r"(?i)pol[ií]gono|parcela|sector|diseminad", rec.get("titulo") or ""):
                return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._zone_geometry(zone)
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_gva = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_gva,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
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
                "titulo": "Tablón de anuncios — licencias y actividades",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos de licencias y actividades en sede espublico",
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
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier?tramite=DECLARACIÓ RESPONSABLE D'OBRES"),
                "fecha_concesion": None,
                "tipo": "declaración responsable de obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Declaración responsable de obras (sede)",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Trámite destacado urbanismo — obras menores",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier?tramite=SOL.LICITUD CERTIFICAT COMPATIBILITAT URBANISTICA"),
                "fecha_concesion": None,
                "tipo": "certificado compatibilidad urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitud certificado compatibilidad urbanística",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámites licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — licencias mayores y menores (web municipal)",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios licencia mayor/menor; web timeout intermitente en CI",
                "origen": "web_tramite",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.urbanismo_url),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo — normas y trámites",
                "fecha": None,
                "tipo": "urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web",
                "nota": "Normas subsidiarias y planes parciales Germanias/Vernisa/Novoperfil",
            },
            {
                "id": _stable_id("proy", self.normas_url),
                "municipio": MUNICIPIO,
                "titulo": "Normas urbanísticas y planos de consulta",
                "fecha": None,
                "tipo": "normativa",
                "url": self.normas_url,
                "source": "ayuntamiento",
                "origen": "web",
            },
            {
                "id": _stable_id("proy", self.transparencia_urbanistica_url),
                "municipio": MUNICIPIO,
                "titulo": "Transparencia — información urbanística",
                "fecha": None,
                "tipo": "transparencia",
                "url": self.transparencia_urbanistica_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
                "nota": "PGOU, planes parciales, PUAM, PLPIF, planes autoprotección",
            },
            {
                "id": _stable_id("proy", "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica"),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica",
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
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "licencias" not in (row.get("procedimiento") or "").lower():
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
        self._enrich_geometry(rec, licencia=True)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower():
                return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento|homologaci[oó]n|sector|plan parcial", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|iate|dogv", blob):
            tipo = "información pública"

        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
        self._enrich_geometry(rec, licencia=False)
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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
        for rec in self._collect_static_web_proyectos():
            add(rec)
        for rec in self._collect_web_crawl_proyectos():
            add(rec)
        for rec in self._collect_icv_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
