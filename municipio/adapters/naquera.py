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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.naquera.es"
SEDE_BASE = "https://naquera.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "Náquera"
ID_PREFIX = "naquera"
INE_MUN = "46181"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "InventarioSuSuz"
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"

DEFAULT_AVISO_SEEDS: tuple[str, ...] = (
    "/va/aviso/el-ple-de-lajuntament-de-naquera-del-passat-dia-24-de-novembre-va-aprovar-unanimitat-el-pla",
    "/va/aviso/el-ple-de-lajuntament-de-naquera-del-passat-dia-29-de-setembre-va-aprovar-unanimitat-la",
    "/es/aviso/el-pleno-del-ayuntamiento-de-naquera-del-pasado-dia-24-de-noviembre-aprobo-por-unanimidad-el",
    "/es/aviso/el-pleno-del-ayuntamiento-de-naquera-del-pasado-dia-29-de-septiembre-aprobo-por-unanimidad-la",
    "/va/pagina/planols",
    "/es/pagina/planos",
    "/va/pagina/urbanitzacions-i-associacions",
)

DEFAULT_PAGINA_SEEDS: tuple[str, ...] = (
    "/va/pagina/planols",
    "/es/pagina/planos",
    "/va/pagina/urbanitzacions-i-associacions",
    "/es/pagina/urbanizaciones-y-asociaciones",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}

RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SUZ|SU|PE|PAI)[\s\-]?(?:[\dA-Z]+(?:[\s,\-yY/]+[\dA-Z]+)*))\b",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla especial|pla urba|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|pr[eè]via)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|cat[aà]leg|protecci[oó]|minimitzaci[oó]|impacte territorial|"
    r"rectificaci[oó]n descriptiva|pl[aà]nol)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|nomenament|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó] fiscal|convenis|festiu local|processos selectius|"
    r"auxiliar administrativo|concurs disfresses|bar[oò]metre|puam|convocatoria de el pleno|"
    r"contrataciones|subvenciones|propuesta de gasto|planificaci[oó]n y ordenaci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://naquera\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_AVISO_LINK = re.compile(
    r'href="((?:/va|/es)/(?:pagina-aviso|aviso)/[^"#?]+)"',
    re.I,
)
RE_PAGINA = re.compile(r'href="((?:/va|/es)/pagina/[^"#?]+)"', re.I)
RE_DATETIME = re.compile(r'datetime="((?:19|20)\d{2}-\d{2}-\d{2})"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean_title(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


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
    for gchild in feat.iter():
        gtag = gchild.tag.split("}", 1)[-1]
        if gtag == "posList" and gchild.text and gchild.text.strip():
            return _gml_poslist_to_polygon(gchild.text.strip())
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pla urba" in n or "plan urba" in n:
        return "plan urbanístico de actuación"
    if "consulta" in n and ("pública" in n or "prèvia" in n or "previa" in n):
        return "consulta pública"
    if "catàleg" in n or "catálogo" in n:
        return "catálogo patrimonial"
    if "plànol" in n or "planol" in n:
        return "plano urbanístico"
    if "licencia ambiental" in n or "llicència ambiental" in n:
        return "licencia ambiental"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class NaqueraAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 Portales + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.aviso_seeds = tuple(self.config.get("aviso_seeds") or DEFAULT_AVISO_SEEDS)
        self.pagina_seeds = tuple(self.config.get("pagina_seeds") or DEFAULT_PAGINA_SEEDS)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer = str(geom_cfg.get("type_name") or ICV_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self.max_wfs_start = int(self.config.get("max_wfs_start", 12000))
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, retries: int | None = None) -> str:
        ua = self.config.get("user_agent", "poc-bocm-naquera/1.0")
        if retries is None:
            retries = int(self.config.get("fetch_retries", 2))
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
                with self._opener.open(req, timeout=int(self.config.get("fetch_timeout_s", 25))) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise last_err or urllib.error.URLError("fetch failed")

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

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

    def _discover_aviso_paths(self) -> list[str]:
        paths: set[str] = set(self.aviso_seeds)
        if not self.config.get("discover_avisos_from_home", False):
            return sorted(paths)
        for lang in ("va", "es"):
            try:
                html = self._fetch(f"{self.web_base}/{lang}")
            except urllib.error.URLError:
                continue
            for m in RE_AVISO_LINK.finditer(html):
                paths.add(m.group(1))
        return sorted(paths)

    def _parse_aviso_page(self, path: str) -> dict[str, Any] | None:
        url = self._abs_web(path)
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        h1 = RE_H1.search(html)
        title_m = RE_TITLE.search(html)
        titulo = _clean_title(h1.group(1) if h1 else (title_m.group(1) if title_m else path))
        titulo = re.sub(r"\s*\|.*(?:Ajuntament|Ayuntamiento).*N[aá]quera.*$", "", titulo, flags=re.I).strip()
        if not titulo or "no trobada" in titulo.lower() or "not found" in titulo.lower():
            return None

        fecha = None
        dt_m = RE_DATETIME.search(html)
        if dt_m:
            fecha = dt_m.group(1)
        if not fecha:
            fecha = _fecha_from_text(html[:8000])

        pdf_urls = [self._abs_web(m.group(1)) for m in RE_PDF.finditer(html)]
        blob = f"{titulo} {path} {' '.join(pdf_urls)}"

        return {
            "titulo": titulo,
            "fecha": fecha,
            "url": url,
            "pdf_urls": pdf_urls,
            "blob": blob,
            "origen": "drupal_aviso",
            "path": path,
        }

    def _collect_drupal_avisos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in self._discover_aviso_paths():
            if path in seen:
                continue
            seen.add(path)
            item = self._parse_aviso_page(path)
            if item:
                rows.append(item)
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.icv_layer,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs}?{params}"

    def _fetch_wfs(self, url: str) -> bytes:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-naquera/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read()

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        while start < self.max_wfs_start:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch_wfs(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall("wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find(f"ms:{self.icv_layer}", _GML_NS)
                if feat is None:
                    feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != self.ine_mun:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _clean_title(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _clean_title(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _clean_title(
                    feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or ""
                )
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_iso(f_aprob or "") if f_aprob else None,
                    "url": VISOR_GVA,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "wfs_id": fid,
                    "pp": pp or None,
                    "ue": ue or None,
                    "origen": "icv_wfs",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            start += 200
            if len(members) < 200:
                break
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
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
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "expte"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _collect_pagina_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.pagina_seeds:
            url = self._abs_web(path)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            h1 = RE_H1.search(html)
            title_m = RE_TITLE.search(html)
            titulo = _clean_title(h1.group(1) if h1 else (title_m.group(1) if title_m else path))
            titulo = re.sub(r"\s*\|.*$", "", titulo).strip()
            blob = f"{titulo} {path}"
            if not RE_PROYECTO.search(blob) and "planol" not in path.lower() and "plano" not in path.lower():
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_text(html[:6000]),
                    "url": url,
                    "blob": blob,
                    "origen": "drupal_pagina",
                }
            )
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
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios publicados en espublico gestiona",
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
                "nota": "Licencias de obra y comunicaciones previas vía sede (sin histórico público)",
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
                "nota": "Requiere identificación Cl@ve; sin listado público",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llicència")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _aviso_is_licencia(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob)) and not (
            RE_PROYECTO.search(blob) and "ambiental" not in blob.lower()
        )

    def _aviso_is_proyecto(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if RE_PROYECTO.search(blob):
            return True
        if RE_LICENCIA.search(blob) and "ambiental" in blob.lower():
            return True
        return False

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
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _aviso_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_licencia(row):
            return None
        blob = row.get("blob") or ""
        tipo = "licencia ambiental" if "ambiental" in blob.lower() else "licencia"
        return {
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
        self._attach_geometry(rec)
        return rec

    def _icv_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"icv:{row.get('wfs_id') or row['titulo']}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
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
        return rec

    def _pagina_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
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
        self._attach_geometry(rec)
        return rec

    def _aviso_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._aviso_is_proyecto(row):
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_aviso"),
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
        for item in self._collect_drupal_avisos():
            rec = self._aviso_to_licencia(item)
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

        for item in self._collect_icv_wfs():
            add(self._icv_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_drupal_avisos():
            add(self._aviso_to_proyecto(item))
        for item in self._collect_pagina_seeds():
            add(self._pagina_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "drupal": sum(1 for r in rows if r.get("origen") in ("drupal_aviso", "drupal_pagina")),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": result.get("with_geometry", 0),
        }
