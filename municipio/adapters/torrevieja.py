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

WEB_BASE = "https://torrevieja.es"
SEDE_BASE = "https://torrevieja.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
EXPOSICION_URL = f"{WEB_BASE}/es/exposicion-publica"
MUNICIPIO = "Torrevieja"
ID_PREFIX = "torrevieja"
INE_MUN = "03133"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    "/es/temas/ciudad/urbanismo",
    "/es/ayuntamiento/consulta-publica-previa",
    "/es/urbanismo/informacion-urbanistica",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}

RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b(?:sector\s+)?(\d{1,3}[a-z]?)\b|"
    r"\b(?:UE|SD|PP|SUZ|SU|PE|PAI)[\s\-]?(?:[\dA-Z]+(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|declaraci[oó]n responsable de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|previa)|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|licencia ambiental|compatibilidad urban|manzana\s+r\d)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|bono consumo|subvenci[oó]n|becas deportistas|dogv n|empleo p[uú]blico|"
    r"calificaci[oó]n definitiva.*ejercicio|bases.*oposici)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://torrevieja\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,6}/\d{4})")
RE_REF_CAT = re.compile(r"(?i)referencia\s+catastral[:\s]*([0-9A-Z]+)")
RE_NODE_LINK = re.compile(r'href="((?:https://torrevieja\.es)?/es/node/\d+)"', re.I)
RE_CONSULTA_LINK = re.compile(r'href="(/es/consulta-publica-previa[^"]*)"', re.I)
RE_H2_SKIP = re.compile(
    r"(?i)^(protocolo de colaboraci|reglamento evaluaci|men[uú] footer|pie de p[aá]gina)",
)


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
        tok = _clean_title(m.group(0))
        if len(tok) >= 2:
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
    if "licencia ambiental" in n:
        return "licencia ambiental"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "estudio de detalle" in n or "manzana r" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "consulta" in n and ("pública" in n or "previa" in n):
        return "consulta pública"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class TorreviejaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 (torrevieja.es) + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.exposicion_url = str(self.config.get("exposicion_url") or EXPOSICION_URL)
        self.seed_pages = tuple(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer = str(geom_cfg.get("type_name") or ICV_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
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
        ua = self.config.get("user_agent", "poc-bocm-torrevieja/1.0")
        if retries is None:
            retries = int(self.config.get("fetch_retries", 2))
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": ua, "Accept-Language": "es;q=0.9"},
            )
            try:
                with self._opener.open(
                    req, timeout=int(self.config.get("fetch_timeout_s", 45))
                ) as resp:
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

    def _collect_exposicion_publica(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.exposicion_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for part in re.split(r"<h2[^>]*>", html)[1:]:
            title_raw = re.sub(r"</h2>.*", "", part, flags=re.S)
            title = _clean_title(_strip_html(title_raw))
            if not title or len(title) < 12 or RE_H2_SKIP.search(title):
                continue
            body = part.split("</h2>", 1)[-1] if "</h2>" in part else ""
            text = _strip_html(body)
            blob = f"{title} {text}"
            if not RE_PROYECTO.search(blob):
                continue
            node_m = RE_NODE_LINK.search(body)
            item_url = node_m.group(1) if node_m else self.exposicion_url
            if item_url.startswith("/"):
                item_url = f"{self.web_base}{item_url}"
            exp_m = RE_EXPTE.search(blob)
            ref_m = RE_REF_CAT.search(blob)
            rows.append(
                {
                    "titulo": title,
                    "fecha": _fecha_from_text(text[:1200]),
                    "url": item_url,
                    "expte": exp_m.group(1) if exp_m else None,
                    "ref_catastral": ref_m.group(1) if ref_m else None,
                    "blob": blob[:2000],
                    "origen": "exposicion_publica",
                }
            )
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in self.seed_pages:
            url = self._abs_web(path)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for m in RE_CONSULTA_LINK.finditer(html):
                href = m.group(1)
                if href in seen:
                    continue
                seen.add(href)
                item_url = self._abs_web(href)
                rows.append(
                    {
                        "titulo": f"Consulta pública — {href.rsplit('/', 1)[-1][:80]}",
                        "fecha": None,
                        "url": item_url,
                        "blob": f"consulta pública {href}",
                        "origen": "consulta_publica",
                    }
                )
        return rows

    def _wfs_page_url(self, start: int) -> str:
        cql = f"cod_ine_mun='{self.ine_mun}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.icv_layer,
                "count": "200",
                "CQL_FILTER": cql,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs}?{params}"

    def _fetch_wfs(self, url: str) -> bytes:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torrevieja/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read()

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        layer_local = self.icv_layer.split(":", 1)[-1]
        while True:
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
                feat = member.find(f"ms:{layer_local}", _GML_NS)
                if feat is None:
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
                    titulo = f"Sector planeamiento {fid}"
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "expte", "ref_catastral"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

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
                "nota": "Edictos publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier.1"),
                "fecha_concesion": None,
                "tipo": "trámite licencia de obra mayor",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitud de licencia de obra mayor (sede)",
                "url": f"{self.sede_base}/dossier.1",
                "source": "ayuntamiento",
                "nota": "Trámite informativo; sin histórico de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "declaración responsable de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Declaración Responsable de Obra (sede)",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc or k in cat for k in ("urban", "licencia", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

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
        self._attach_geometry(rec)
        return rec

    def _exposicion_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and "ambiental" not in blob.lower():
            return None
        key = row.get("expte") or row["url"]
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia ambiental" if "ambiental" in blob.lower() else "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "exposicion_publica",
        }
        self._attach_geometry(rec)
        return rec

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row.get("titulo", "")
        rec = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": row.get("origen"),
        }
        if row.get("ref_catastral"):
            rec["ref_catastral"] = row["ref_catastral"]
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "urban" not in proc:
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
        for item in self._collect_exposicion_publica():
            rec = self._exposicion_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion_publica"),
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
        for item in self._collect_exposicion_publica():
            rec = self._exposicion_to_licencia(item)
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
        for item in self._collect_exposicion_publica():
            add(self._generic_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion_publica"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
