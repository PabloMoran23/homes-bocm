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

WEB_BASE = "https://www.higueruelas.es"
SEDE_BASE = "https://higueruelas.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier"
MUNICIPIO = "Higueruelas"
ID_PREFIX = "higueruelas"
COD_INE_MUN = "46129"

PLANEAMIENTO_URL = f"{WEB_BASE}/transparencia/planeamiento-urbanistico"
PGOU_NOTICIA_URL = f"{WEB_BASE}/noticia/plan-general-ordenacion-urbana-higueruelas-pgou"
TRAMITES_URL = f"{WEB_BASE}/transparencia/tramites"
IMPRESOS_URL = f"{WEB_BASE}/transparencia/descargar-impresos"
GVA_PLANEAMIENTO_URL = (
    "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica"
)
VISOR_GVA_URL = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000, 13500]
ICV_MAX_EMPTY_PAGES = 6

DEFAULT_SEED_PAGES: list[str] = [
    PLANEAMIENTO_URL,
    PGOU_NOTICIA_URL,
    TRAMITES_URL,
    IMPRESOS_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|criterios? (?:est[eé]ticos|interpretativos))",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"pad[ró]n|empadron|modificaci[oó]n de cr[eé]ditos|presupuest|subvenci[oó]n|"
    r"empleo p[uú]blico|bolsa de (?:empleo|trabajo)|festiv|fiesta)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://higueruelas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.higueruelas\.es)?/sites/www\.higueruelas\.es/files/[^"]+\.(?:pdf|PDF))"',
    re.I,
)
RE_NOTICIA_HREF = re.compile(r'href="(/noticia/[^"#?]+)"', re.I)
RE_AVISO_HREF = re.compile(r'href="(/(?:noticia|transparencia)/[^"#?]+)"', re.I)


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


def _abs_web_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{WEB_BASE}{path}"


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
    if "criterio" in n and "estet" in n:
        return "normativa estética"
    return "planeamiento"


class HigueruelasAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede espublico gestiona (sin capa ICV publicada aún)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))
        self.fetch_retries = int(self.config.get("fetch_retries", 3))
        self.fetch_timeout = int(self.config.get("fetch_timeout_s", 45))
        self.web_fetch_retries = int(self.config.get("web_fetch_retries", 1))
        self.web_fetch_timeout = int(self.config.get("web_fetch_timeout_s", 25))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.icv_max_empty_pages = int(geom_cfg.get("max_empty_pages") or ICV_MAX_EMPTY_PAGES)
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

    def _fetch_bytes(
        self,
        url: str,
        *,
        timeout: int | None = None,
        retries: int | None = None,
    ) -> bytes:
        if timeout is None:
            timeout = self.fetch_timeout
        if retries is None:
            retries = self.fetch_retries
        ua = self.config.get("user_agent", "poc-bocm-higueruelas/1.0")
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.75 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch(
        self,
        url: str,
        *,
        timeout: int | None = None,
        retries: int | None = None,
    ) -> str:
        return self._fetch_bytes(url, timeout=timeout, retries=retries).decode(
            "utf-8", errors="replace"
        )

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        return json.loads(self._fetch_bytes(url, timeout=timeout))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=60)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

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
        empty_pages = 0
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
                data = self._fetch_json(url, timeout=60)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            batch = data.get("features") or []
            if not batch:
                break
            hits = 0
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
                hits += 1
                grouped.setdefault((den, exp), []).append(feat)
            if hits:
                empty_pages = 0
            else:
                empty_pages += 1
                if grouped and empty_pages >= self.icv_max_empty_pages:
                    break
                if not grouped and empty_pages >= self.icv_max_empty_pages:
                    break

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

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        best: tuple[float, dict[str, Any]] | None = None
        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif "PLAN GENERAL" in norm and "PLAN GENERAL" in den:
                score = 80.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)
        if best and best[0] >= 20:
            return best[1]
        return None

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
                "url": VISOR_GVA_URL,
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

    def _collect_web_links(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, origen: str, tipo: str = "urbanismo", fecha: str | None = None) -> None:
            full = _abs_web_url(url)
            if full in seen_urls:
                return
            seen_urls.add(full)
            blob = f"{titulo} {full}"
            rec = {
                "id": _stable_id("proy", full),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha or _parse_fecha_dmy(blob),
                "tipo": tipo,
                "url": full,
                "source": "ayuntamiento",
                "origen": origen,
            }
            rows.append(rec)

        extra_pages: list[str] = []
        web_failures = 0
        for page in self.seed_pages[: self.max_crawl_pages]:
            if web_failures >= 2:
                break
            try:
                html = self._fetch(
                    page,
                    timeout=self.web_fetch_timeout,
                    retries=self.web_fetch_retries,
                )
            except urllib.error.URLError:
                web_failures += 1
                continue

            h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            page_title = _strip_html(h1.group(1)) if h1 else page.rsplit("/", 1)[-1]
            if RE_PROYECTO.search(page_title) or RE_LICENCIA.search(page_title):
                tipo = "licencia" if RE_LICENCIA.search(page_title) and not RE_PROYECTO.search(page_title) else "urbanismo"
                if "pgou" in page_title.lower() or "plan general" in page_title.lower():
                    tipo = "planeamiento"
                add(page, page_title, "web_page", tipo)

            for m in RE_NOTICIA_HREF.finditer(html):
                path = m.group(1)
                if path not in extra_pages:
                    extra_pages.append(path)
            for m in RE_AVISO_HREF.finditer(html):
                path = m.group(1)
                if path not in extra_pages:
                    extra_pages.append(path)

            for m in RE_PDF_HREF.finditer(html):
                pdf_path = m.group(1)
                pdf_url = _abs_web_url(pdf_path)
                titulo = unescape(Path(pdf_path.split("/files/", 1)[-1]).stem.replace("%20", " "))
                titulo = re.sub(r"[_-]+", " ", titulo).strip()
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                tipo = "licencia" if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo) else "urbanismo"
                if "pgou" in titulo.lower() or "plan general" in titulo.lower():
                    tipo = "planeamiento"
                add(pdf_url, titulo, "web_pdf", tipo)

        for path in extra_pages[: self.max_crawl_pages]:
            if web_failures >= 2:
                break
            try:
                html = self._fetch(
                    _abs_web_url(path),
                    timeout=self.web_fetch_timeout,
                    retries=self.web_fetch_retries,
                )
            except urllib.error.URLError:
                web_failures += 1
                continue
            h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            titulo = _strip_html(h1.group(1)) if h1 else path.rsplit("/", 1)[-1]
            if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                continue
            tipo = "licencia" if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo) else "urbanismo"
            if "pgou" in titulo.lower():
                tipo = "planeamiento"
            add(path, titulo, "web_aviso", tipo)
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = _abs_web_url(m.group(1))
                pdf_title = unescape(Path(m.group(1).split("/files/", 1)[-1]).stem.replace("%20", " "))
                pdf_title = re.sub(r"[_-]+", " ", pdf_title).strip() or titulo
                add(pdf_url, pdf_title, "web_pdf", tipo)

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
                "titulo": "Tablón de anuncios — sede electrónica Higueruelas",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos de licencias y actividades en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Licencias, DR y comunicaciones previas vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", IMPRESOS_URL),
                "fecha_concesion": None,
                "tipo": "impresos urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Descargar impresos — trámites urbanismo",
                "url": IMPRESOS_URL,
                "source": "ayuntamiento",
                "nota": "Formularios licencias obra mayor/menor y actividades",
                "origen": "web_tramite",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", PLANEAMIENTO_URL),
                "municipio": MUNICIPIO,
                "titulo": "Transparencia — planeamiento urbanístico",
                "fecha": None,
                "tipo": "transparencia",
                "url": PLANEAMIENTO_URL,
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("proy", PGOU_NOTICIA_URL),
                "municipio": MUNICIPIO,
                "titulo": "Plan General de Ordenación Urbana de Higueruelas (PGOU)",
                "fecha": "2026-06-25",
                "tipo": "PGOU",
                "url": PGOU_NOTICIA_URL,
                "source": "ayuntamiento",
                "origen": "web_noticia",
                "nota": "PGOU aprobado; memoria, normas y planos en web municipal",
            },
            {
                "id": _stable_id("proy", GVA_PLANEAMIENTO_URL),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": GVA_PLANEAMIENTO_URL,
                "source": "ayuntamiento",
                "origen": "datos_abiertos",
            },
            {
                "id": _stable_id("proy", VISOR_GVA_URL),
                "municipio": MUNICIPIO,
                "titulo": "Visor GVA — planeamiento urbanístico",
                "fecha": None,
                "tipo": "visor GIS",
                "url": VISOR_GVA_URL,
                "source": "ayuntamiento",
                "origen": "visor",
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
        if re.search(r"(?i)planeamiento|homologaci[oó]n|sector|plan parcial|pgou", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|dogv", blob):
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
        for item in self._collect_web_links():
            if item.get("tipo") != "licencia":
                continue
            lic = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "licencia / anuncio",
                "distrito": None,
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item.get("origen"),
            }
            if lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
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
        for rec in self._collect_icv_proyectos():
            add(rec)
        for item in self._collect_web_links():
            if item.get("tipo") == "licencia":
                continue
            self._enrich_geometry(item, licencia=False)
            add(item)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
