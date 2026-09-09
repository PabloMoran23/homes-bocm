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

BASE = "http://www.albalatdelssorells.net"
API_BASE = "https://api.digitalvalue.es/albalatdelssorells/collections"
SEDE_BASE = "https://albalatdelssorells.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
DOSSIER_URL = f"{SEDE_BASE}/dossier"
MUNICIPIO = "Albalat dels Sorells"
ID_PREFIX = "albalat-dels-sorells"
INE_MUN = "46009"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"

HUB_SLUGS = {
    "urbanismo",
    "servicios",
    "serveis",
    "transparencia",
    "participacion-ciudadana",
    "plan-de-gobierno",
    "pla-de-govern",
}

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|actuaci[oó]n urban|informe urban|certificat.*urban|"
    r"recepci[oó]n.*obra|modificaci[oó]n.*llicencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|normativa urban|plantejament|"
    r"homologaci[oó]n|obras? (?:p[uú]blicas?|en curso)|licitaci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|padrones|bop\b|boe\b|pleno|empleo p[uú]blico|"
    r"modificaciones presupuestarias|festivos local)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://albalatdelssorells\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRAMITE = re.compile(
    r'href="(https://albalatdelssorells\.sedelectronica\.es/catalog/t/[a-f0-9\-]+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|SEQUIAR)[\s\-]?(?:IND\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("es", "und", "va", "ca"):
            if value.get(key):
                return str(value[key])
        for v in value.values():
            if v:
                return str(v)
        return ""
    return str(value or "")


def _slug_value(item: dict[str, Any]) -> str:
    data = item.get("data") or {}
    slug = data.get("slug")
    if isinstance(slug, dict):
        return _localized(slug).strip("/")
    return str(slug or "").strip("/")


def _title(item: dict[str, Any]) -> str:
    return _clean(_localized(item.get("title")))


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _article_fecha(item: dict[str, Any]) -> str | None:
    period = item.get("publishPeriod") or {}
    start = period.get("start")
    if start and "T" in str(start):
        return str(start).split("T", 1)[0]
    for key in ("date", "modified", "updated", "created"):
        raw = item.get(key)
        if not raw:
            continue
        text = str(raw)
        if "T" in text:
            return text.split("T", 1)[0]
        parsed = _parse_fecha_dmy(text)
        if parsed:
            return parsed
    return _parse_fecha_dmy(_title(item))


def _article_url(item: dict[str, Any]) -> str:
    meta = (item.get("meta") or {}).get("uri") or {}
    for key in ("es", "und", "ca"):
        uri = meta.get(key)
        if uri:
            return str(uri).rstrip("/")
    slug = _slug_value(item)
    if slug:
        return f"{BASE}/es/articulos/{slug}"
    return f"{BASE}/es/articulos/{item.get('_id', '')}"


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "normativa" in n:
        return "normativa urbanística"
    if "obras en curso" in n or "obres en curs" in n:
        return "obras en curso"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "licitaci" in n:
        return "obras públicas"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean(m.group(1))
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
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class AlbalatDelsSorellsAyuntamientoAdapter(AyuntamientoAdapter):
    """Digital Value CMS + sede espublico gestiona + ICV WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.api_base = str(self.config.get("api_base") or API_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
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
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-albalat-dels-sorells/1.0")},
            )
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                clean = {k: v for k, v in row.items() if v is not None}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _fetch_all_articulos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        limit = 200
        while True:
            url = f"{self.api_base}/articulos?limit={limit}&offset={offset}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("items", []) if isinstance(data, dict) else data
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return rows

    def _fetch_article(self, article_id: str) -> dict[str, Any] | None:
        try:
            data = self._fetch_json(f"{self.api_base}/articulos/{article_id}")
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _iter_nodes_group(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for group in item.get("nodesGroup") or []:
            for node in group.get("nodes") or []:
                if isinstance(node, dict):
                    nodes.append(node)
        return nodes

    def _is_proyecto_article(self, item: dict[str, Any]) -> bool:
        slug = _slug_value(item).lower()
        if slug in HUB_SLUGS:
            return False
        title = _title(item)
        cats = [str(c).lower() for c in (item.get("categories") or [])]
        node_types = [str(c).lower() for c in (item.get("nodeTypes") or [])]
        blob = f"{title} {slug} {' '.join(cats)} {' '.join(node_types)}"
        if RE_NOISE.search(blob):
            return False
        if RE_PROYECTO.search(blob):
            return True
        if item.get("filesGroup") and (
            "urbanismo" in cats
            or "transparencia" in node_types
            or "pgou" in slug
            or "normativa" in slug
        ):
            return True
        return False

    def _article_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        title = _title(item)
        url = _article_url(item)
        blob = title
        files: list[str] = []
        for group in item.get("filesGroup") or []:
            if not isinstance(group, dict):
                continue
            for f in group.get("files") or []:
                if isinstance(f, dict):
                    ft = str(f.get("title") or "")
                else:
                    ft = str(f or "")
                if ft:
                    files.append(ft)
                    blob = f"{blob} {ft}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": _article_fecha(item),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "slug": _slug_value(item),
            "origen": "digitalvalue_api",
        }
        if files:
            rec["documentos"] = files[:20]
        self._attach_geometry(rec)
        return rec

    def _collect_articulos_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in self._fetch_all_articulos():
            candidates = [item]
            for node in self._iter_nodes_group(item):
                candidates.append(node)
            for cand in candidates:
                if not self._is_proyecto_article(cand):
                    continue
                rec = self._article_to_proyecto(cand)
                if rec["id"] in seen_ids:
                    continue
                seen_ids.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, timeout=90)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title in RE_TRAMITE.findall(html):
            titulo = _clean(unescape(title))
            rows.append({"titulo": titulo, "url": href, "origen": "sede_tramite"})
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
                cells[cm.group(1)] = _clean(re.sub(r"<[^>]+>", " ", cm.group(2)))

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

    def _wfs_page_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _parse_wfs_member(self, member: ET.Element, *, layer: str) -> dict[str, Any] | None:
        feat = None
        for tag in (f"{{{_GML_NS['ms']}}}{layer}", f"{{{_GML_NS['ms']}}}InventarioSuSuz"):
            feat = member.find(tag)
            if feat is not None:
                break
        if feat is None:
            for child in member:
                if child.tag.endswith("InventarioSuSuz") or child.tag.endswith("Zonificacion"):
                    feat = child
                    break
        if feat is None:
            return None

        cod = (
            feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
            or feat.findtext("ms:COD_INE_MUN", default="", namespaces=_GML_NS)
        )
        if cod and cod != self.cod_ine_mun:
            return None

        fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
        pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
        ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
        denom = _clean(
            feat.findtext("ms:denominaci", default="", namespaces=_GML_NS)
            or feat.findtext("ms:denominaci_val", default="", namespaces=_GML_NS)
            or ""
        )
        clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"

        geom = _gml_feature_to_geojson(feat)
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob,
            "url": self._wfs_page_url(self.icv_layer_su, 0),
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "clasificacion": clas or None,
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = rec["url"]
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"), (self.icv_layer_zon, "Zonificacion")):
            start = 0
            while start < 12000:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=90)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                for member in members:
                    rec = self._parse_wfs_member(member, layer=layer.split(".")[-1])
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                if len(members) < 200:
                    break
                start += 200
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue", "slug"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Ficha procedimental sede; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            proc = (row.get("procedimiento") or "").lower()
            if "licenc" not in proc and "actuaci" not in proc:
                return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "edicto tablón",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "pp",
            "ue",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "documentos",
            "slug",
            "expte",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower():
                return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "urban" not in proc and "actuaci" not in proc:
            return None
        row = {**row, "expte": row.get("expediente")}
        return self._to_proyecto(row)

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
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
                "nota": "Requiere certificado digital; sin listado histórico público",
                "origen": "sede_tramite",
            },
        ]

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
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
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._collect_articulos_proyectos():
            add(item)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "digitalvalue": sum(1 for r in rows if r.get("origen") == "digitalvalue_api"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
