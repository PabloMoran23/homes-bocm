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

WEB_BASE = "https://www.gatadegorgos.org"
SEDE_BASE = "https://gatadegorgos.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
PLANEJAMENT_URL = f"{WEB_BASE}/ajuntament/planejament/"
TAULER_URL = f"{WEB_BASE}/category/noticies/tauler-danuncis/"
SOLICITUDS_URL = f"{WEB_BASE}/ajuntament/solicituds-i-impresos/"
GVA_BASE = (
    "https://politicaterritorial.gva.es/auto/urbanismo/reg-planeamiento/"
    "2%20ALICANTE/03071%20GATA%20DE%20GORGOS/"
)
MUNICIPIO = "Gata de Gorgos"
ID_PREFIX = "gata-de-gorgos"
COD_INE_MUN = "03071"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(0, 14000, 500))
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|autoritzaci[oó]|inicio de obra|"
    r"obra (?:mayor|menor)|formularis d'autoritzacions urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planejament|plan (?:parcial|especial|general)|pgou|pla especial|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|pr[eè]via|òmnibus)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|reforma interior|"
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|nnss|p\. diferido|p\. general)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|nomenament|convocatoria.*empleo|"
    r"cobranza iae|padrones|modificaci[oó]n de cr[eé]ditos|modificacions pressupost|"
    r"suplemento de cr[eé]dito|generaci[oó] de cr[eé]dit|exp mod cred|"
    r"presupuest|pressupost|subvenci[oó]n|empleo p[uú]blico|festes|festa|residus|pleno|ple)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://gatadegorgos\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC\"PLANS]+)")
RE_WP_ARTICLE = re.compile(r"<article[^>]*>(.*?)</article>", re.I | re.S)
RE_WP_LINK = re.compile(r'href="(https://www\.gatadegorgos\.org/[^"#?]+/?)"', re.I)
RE_WP_TITLE = re.compile(
    r'class="[^"]*entry-title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_DATETIME = re.compile(r'datetime="((?:19|20)\d{2}-\d{2}-\d{2})"', re.I)
RE_DIR_LINK = re.compile(r'<a href="([^"]+)">([^<]+)</a>', re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
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


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


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


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "plan general" in n or "pgou" in n or "p. general" in n:
        return "PGOU"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "plan parcial" in n or "homologaci" in n:
        return "plan parcial"
    if "reforma interior" in n or "sector" in n:
        return "plan parcial"
    if "modificaci" in n and ("nnss" in n or "subsidiari" in n):
        return "modificación normas subsidiarias"
    if "consulta" in n:
        return "consulta pública"
    if "planejament" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class GataDeGorgosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede espublico gestiona + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.planejament_url = str(self.config.get("planejament_url") or PLANEJAMENT_URL)
        self.tauler_url = str(self.config.get("tauler_url") or TAULER_URL)
        self.gva_base = str(self.config.get("gva_base") or GVA_BASE)
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

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        ua = self.config.get("user_agent", "poc-bocm-gata-de-gorgos/1.0")
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": ua,
                    "Accept-Language": "ca,es;q=0.9",
                },
            )
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise last_err or urllib.error.URLError("fetch failed")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-gata-de-gorgos/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page in range(1, 4):
            url = self.tauler_url if page == 1 else f"{self.tauler_url}page/{page}/"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            found = 0
            for article in RE_WP_ARTICLE.findall(html):
                link_m = RE_WP_LINK.search(article)
                title_m = RE_WP_TITLE.search(article)
                date_m = RE_DATETIME.search(article)
                if not link_m:
                    continue
                post_url = link_m.group(1).rstrip("/") + "/"
                if post_url in seen_urls:
                    continue
                seen_urls.add(post_url)
                titulo = _clean_title(title_m.group(1) if title_m else post_url)
                titulo = re.sub(r"\s*\|.*Ajuntament.*$", "", titulo, flags=re.I).strip()
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": date_m.group(1) if date_m else None,
                        "url": post_url,
                        "blob": titulo,
                        "origen": "wp_tauler",
                    }
                )
                found += 1
            if found == 0:
                break
        return rows

    def _collect_gva_entries(self, base_url: str, prefix: str = "") -> list[dict[str, Any]]:
        try:
            html = self._fetch(base_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_DIR_LINK.finditer(html):
            href, label = m.group(1), unescape(m.group(2)).strip()
            if href in ("?C=N;O=D", "../") or label in ("Name", ".."):
                continue
            full_url = urllib.parse.urljoin(base_url, href)
            titulo = f"{prefix}{label}".strip()
            blob = f"{titulo} {full_url}"
            if not RE_PROYECTO.search(blob) and "03071" not in label:
                if not href.endswith("/"):
                    continue
            if href.endswith("/"):
                sub_prefix = f"{label} — " if label else prefix
                rows.extend(self._collect_gva_entries(full_url, sub_prefix))
            else:
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_text(label),
                        "url": full_url,
                        "blob": blob,
                        "origen": "gva_planeamiento",
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
        sector = sector_m.group(1).upper().strip('"') if sector_m else None
        best: tuple[float, dict[str, Any]] | None = None

        for zone in self._collect_icv_zones():
            den = _normalize_title(zone.get("denominaci") or "")
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif sector and sector in den:
                score = 80.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if "PLANS" in norm and "PLANS" in den:
                score += 30.0
            if "NORMAS SUBSIDIARIAS" in norm and "NORMAS SUBSIDIARIAS" in den:
                score += 25.0
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
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": VISOR_GVA,
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
                "titulo": "Tablón de anuncios — sede electrónica",
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
                "nota": "Promptuari formularis autoritzacions urbanístiques 2026",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", SOLICITUDS_URL),
                "fecha_concesion": None,
                "tipo": "formularios licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sol·licituds i impresos — àrea urbanisme",
                "url": SOLICITUDS_URL,
                "source": "ayuntamiento",
                "nota": "Formularis urbanisme 2026 via web corporativa",
                "origen": "web_tramite",
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
                "id": _stable_id("proy", self.planejament_url),
                "municipio": MUNICIPIO,
                "titulo": "Planejament urbanístic — Ajuntament de Gata de Gorgos",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.planejament_url,
                "source": "ayuntamiento",
                "origen": "web_info",
            },
            {
                "id": _stable_id("proy", self.gva_base),
                "municipio": MUNICIPIO,
                "titulo": "Registro planeamiento GVA — Gata de Gorgos (03071)",
                "fecha": None,
                "tipo": "normativa",
                "url": self.gva_base,
                "source": "ayuntamiento",
                "origen": "gva_planeamiento",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llicència")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _post_is_licencia(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob)) and not (
            RE_PROYECTO.search(blob) and "ambiental" not in blob.lower()
        )

    def _post_is_proyecto(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob))

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
        rec = {
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

    def _post_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._post_is_licencia(row):
            return None
        blob = row.get("blob") or ""
        tipo = "autorización urbanística" if "autoritz" in blob.lower() else "licencia"
        rec = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec, licencia=True)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _post_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._post_is_proyecto(row):
            return None
        blob = row.get("blob") or ""
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _gva_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "gva_planeamiento",
        }
        self._enrich_geometry(rec)
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
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wp": sum(1 for r in rows if r.get("origen") == "wp_tauler"),
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
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
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
        for item in self._collect_gva_entries(self.gva_base):
            add(self._gva_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "gva": sum(1 for r in rows if r.get("origen") == "gva_planeamiento"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wp": sum(1 for r in rows if r.get("origen") == "wp_tauler"),
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
