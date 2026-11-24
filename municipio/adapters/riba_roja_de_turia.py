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

SEDE_BASE = "https://oficinavirtual.ribarroja.es/PortalCiudadania"
WEB_BASE = "https://www.ribarroja.es"
TABLON_URL = f"{WEB_BASE}/es/ayuntamiento/tablon_de_anuncios"
TRAMITES_URB_URL = f"{SEDE_BASE}/tramites/browser.do?formAction=btList&s=11"
TABLON_EDICTOS_URL = f"{SEDE_BASE}/tablonEdictos.do"
PLANEAMIENTO_URL = f"{WEB_BASE}/planeamiento_en_vigor/planeamiento_de_desarrollo"
TRANSP_URB_URL = (
    f"{WEB_BASE}/es/portal_de_transparencia/transparencia_urbanismo_obras_publicas_medioambiente"
)
URBANISME_URL = f"{WEB_BASE}/es/seccion/urbanisme"
VISOR_GVA_URL = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
MUNICIPIO = "Riba-roja de Túria"
ID_PREFIX = "riba-roja-de-turia"
COD_INE_MUN = "46214"

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
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|e[oó]lic|iate|divendres|maestrat)",
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
RE_TABLON_LINK = re.compile(
    r'field__item"><a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_DATETIME = re.compile(r'datetime="((?:19|20)\d{2}-\d{2}-\d{2})', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+)")
RE_NORMATIVA_LINK = re.compile(
    r'href="([^"]+)"[^>]*>([^<]{8,200})</a>',
    re.I | re.S,
)
RE_BOP_DATE = re.compile(r"BOP[-\s]*(\d+)\s+de\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.I)


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


def _fecha_from_bop(text: str) -> str | None:
    m = RE_BOP_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(4)), int(m.group(3)), int(m.group(2))).strftime("%Y-%m-%d")
    except ValueError:
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
    if "reparcel" in n or "urbanizaci" in n:
        return "reparcelación"
    if "ordenanza" in n or "licencia" in n:
        return "normativa"
    return "planeamiento"


class RibaRojaDeTuriaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales (Dival) + oficina virtual + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.tramites_urb_url = str(self.config.get("tramites_urb_url") or TRAMITES_URB_URL)
        self.tablon_edictos_url = str(self.config.get("tablon_edictos_url") or TABLON_EDICTOS_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.transp_urb_url = str(self.config.get("transp_urb_url") or TRANSP_URB_URL)
        self.urbanisme_url = str(self.config.get("urbanisme_url") or URBANISME_URL)
        self.visor_gva_url = str(self.config.get("visor_gva_url") or VISOR_GVA_URL)
        self.max_tablon_detail_fetches = int(self.config.get("max_tablon_detail_fetches", 40))
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-riba-roja-de-turia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-riba-roja-de-turia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{self.web_base}{href}"
        return f"{self.web_base}/{href}"

    def _collect_drupal_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        detail_budget = self.max_tablon_detail_fetches
        for href, raw_title in RE_TABLON_LINK.findall(html):
            titulo = _strip_html(raw_title)
            if not titulo or len(titulo) < 8:
                continue
            url = self._abs_url(href)
            blob = f"{titulo} {url}"
            fecha: str | None = None
            if detail_budget > 0 and "/contenidos/" in url:
                if RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob):
                    try:
                        detail = self._fetch(url)
                        dm = RE_DATETIME.search(detail)
                        if dm:
                            fecha = dm.group(1)
                        detail_budget -= 1
                    except urllib.error.URLError:
                        pass
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": fecha,
                    "blob": blob,
                    "origen": "tablon_drupal",
                }
            )
        return rows

    def _collect_planeamiento_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in (self.planeamiento_url, self.transp_urb_url, self.urbanisme_url):
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for pdf_href in RE_PDF.findall(html):
                url = self._abs_url(pdf_href)
                name = Path(urllib.parse.unquote(url)).name
                titulo = f"Documento urbanismo: {name}"
                blob = f"{titulo} {url}"
                if not RE_PROYECTO.search(blob) and "planeam" not in name.lower():
                    continue
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_expediente(name),
                    "tipo": _proyecto_tipo(titulo),
                    "url": seed,
                    "pdf_url": url,
                    "source": "ayuntamiento",
                    "origen": "web_pdf",
                }
                self._enrich_geometry(rec, licencia=False)
                rows.append(rec)
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
            elif "MASA" in norm and "MASA" in den:
                score = 70.0
            elif "SAN RAFAEL" in norm and "SAN RAFAEL" in den:
                score = 75.0
            elif "PEYLAND" in norm and "PEYLAND" in den:
                score = 75.0
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
            "geometry_crs": "EPSG:4326",
            "geometry_axis_order": "xy",
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
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": self.visor_gva_url,
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

    def _collect_normativa_web(self) -> list[dict[str, Any]]:
        return self._collect_planeamiento_pdfs()

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_urb_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo (URB)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Oficina virtual — trámites URB (licencias y DR)",
                "url": self.tramites_urb_url,
                "source": "ayuntamiento",
                "nota": "URB 01–13; presentación telemática con certificado",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.tablon_edictos_url),
                "fecha_concesion": None,
                "tipo": "tablón edictos sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — oficina virtual",
                "url": self.tablon_edictos_url,
                "source": "ayuntamiento",
                "nota": "Iframe sede propia; sin listado HTML scrapeable",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios web",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — portal municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Listado Drupal portales7-weblink",
                "origen": "web_tablon",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.planeamiento_url),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento en vigor — desarrollo y estudios de detalle",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.planeamiento_url,
                "source": "ayuntamiento",
                "origen": "web_normativa",
            },
            {
                "id": _stable_id("proy", self.transp_urb_url),
                "municipio": MUNICIPIO,
                "titulo": "Transparencia — urbanismo, obras públicas y medioambiente",
                "fecha": None,
                "tipo": "normativa",
                "url": self.transp_urb_url,
                "source": "ayuntamiento",
                "origen": "web_normativa",
            },
            {
                "id": _stable_id("proy", self.urbanisme_url),
                "municipio": MUNICIPIO,
                "titulo": "Sección urbanismo — portal municipal",
                "fecha": None,
                "tipo": "normativa",
                "url": self.urbanisme_url,
                "source": "ayuntamiento",
                "origen": "web_normativa",
            },
            {
                "id": _stable_id("proy", self.visor_gva_url),
                "municipio": MUNICIPIO,
                "titulo": "Visor GVA — zonificación urbanística ICV",
                "fecha": None,
                "tipo": "visor GIS",
                "url": self.visor_gva_url,
                "source": "ayuntamiento",
                "origen": "visor",
            },
            {
                "id": _stable_id(
                    "proy",
                    "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica",
                ),
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
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia urbanística"
        if re.search(r"(?i)criterios interpretativos", blob):
            tipo = "normativa licencias"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row["url"]
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
            return None
        if not RE_PROYECTO.search(blob):
            return None

        tipo = _proyecto_tipo(row.get("titulo") or blob)
        if re.search(r"(?i)informaci[oó]n p[uú]blica|consulta p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)convenio urban", blob):
            tipo = "convenio urbanístico"

        key = row["url"]
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
        for item in self._collect_drupal_tablon():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_normativa")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_drupal_tablon():
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
        for rec in self._collect_icv_proyectos():
            add(rec)
        for rec in self._collect_normativa_web():
            add(rec)
        for item in self._collect_drupal_tablon():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "normativa": sum(1 for r in rows if r.get("origen") == "web_normativa"),
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
