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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plantejament|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|unidad de ejecuci[oó]n|\bue[\.\-\s]*\d+|\bsector\s*\d+|"
    r"actuaci[oó]n urban|concessi[oó] demanial|pgom)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"modificaci[oó]n de cr[eé]ditos|subvenci[oó]n|presupuest|jurado|"
    r"polic[ií]a local|igualdad|representaci[oó]n teatral|fiestas)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://[^/]+\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.(?:pdf|zip)[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector|ue|p\.?\s*|unidad de ejecuci[oó]n)\s*([A-Z]?\s*\d+)\b",
)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


@dataclass
class TownConfig:
    id_prefix: str
    municipio: str
    ine: str
    web_base: str
    sede_kind: str  # sedipualba | espublico
    sede_base: str
    board_url: str | None = None
    tablon_rss: str | None = None
    seed_pages: list[str] = field(default_factory=list)
    centroid: tuple[float, float] = (0.0, 0.0)


TOWNS: list[TownConfig] = [
    TownConfig(
        id_prefix="benicarlo",
        municipio="Benicarló",
        ine="12018",
        web_base="https://www.benicarlo.org",
        sede_kind="sedipualba",
        sede_base="https://benicarlo.sedipualba.es",
        tablon_rss="https://benicarlo.sedipualba.es/tablondeanuncios/tablon_rss.aspx",
        seed_pages=[
            "https://benicarlo.sedipualba.es/tablondeanuncios/default.aspx",
            "https://benicarlo.sedipualba.es/catalogoservicios.aspx",
        ],
        centroid=(40.4208, 0.4275),
    ),
    TownConfig(
        id_prefix="vinaros",
        municipio="Vinaròs",
        ine="12138",
        web_base="https://www.vinaros.es",
        sede_kind="espublico",
        sede_base="https://vinaros.sedelectronica.es",
        board_url="https://vinaros.sedelectronica.es/board",
        seed_pages=[
            "https://urbanisme.vinaros.es/es/contenido/planeamiento-urbanistico-municipal",
            "https://www.vinaros.es/es/contenido/gobierno-y-transparencia",
        ],
        centroid=(40.4703, 0.4756),
    ),
    TownConfig(
        id_prefix="benijofar",
        municipio="Benijófar",
        ine="03012",
        web_base="https://www.benijofar.es",
        sede_kind="espublico",
        sede_base="https://benijofar.sedelectronica.es",
        board_url="https://benijofar.sedelectronica.es/board",
        tablon_rss="https://www.benijofar.es/category/noticias/tablon/feed/",
        seed_pages=[
            "https://www.benijofar.es/category/noticias/tablon/",
        ],
        centroid=(38.0778, -0.7344),
    ),
]


def _stable_id(prefix: str, kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or re.search(r"\bsector\s*\d+", b):
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgou" in b or "plan general" in b or "modificaci" in b and "puntual" in b:
        return "planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if re.search(r"\bue[\.\-\s]*\d+", b) or "unidad de ejecuci" in b:
        return "unidad de ejecución"
    if "concessi" in b and "demanial" in b:
        return "concesión demanial"
    if "obra" in b or "asfalt" in b or "paviment" in b:
        return "obra urbanística"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class BenicarloVinarosBenijofarAyuntamientoAdapter(AyuntamientoAdapter):
    """Cola compuesta CV: sedipualba (Benicarló) + espublico (Vinaròs/Benijófar) + ICV WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TOWNS[0].web_base)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_by_ine: dict[str, list[dict[str, Any]]] = {}
        self._wfs_index: dict[str, dict[str, dict[str, Any]]] = {}

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benicarlo-vinaros-benijofar/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str) -> str:
        return unescape(urllib.parse.urljoin(f"{base.rstrip('/')}/", href))

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

    def _collect_tablon_rss(self, town: TownConfig) -> list[dict[str, Any]]:
        if not town.tablon_rss:
            return []
        try:
            raw = self._fetch(town.tablon_rss)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = _strip_html(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "blob": title,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _collect_espublico_board(self, town: TownConfig) -> list[dict[str, Any]]:
        if not town.board_url:
            return []
        try:
            html = self._fetch(town.board_url)
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

            if not documento or documento in ("Documento", "Document"):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else town.board_url
            if url.startswith("/"):
                url = f"{town.sede_base}{url}"

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

    def _collect_seed_docs(self, town: TownConfig) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in town.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            page_title = _strip_html(h1_m.group(1)) if h1_m else page_url
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                doc_url = self._abs_url(href, town.web_base if href.startswith("/") else page_url)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                name = unescape(urllib.parse.unquote(Path(href).name))
                titulo = f"{page_title} — {name}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name),
                        "url": doc_url,
                        "blob": f"{titulo} {page_url}",
                        "origen": "web_seed",
                    }
                )
            for m in re.finditer(r'<article[^>]*>.*?</article>', html, re.I | re.S):
                block = m.group(0)
                link_m = re.search(r'href="(https?://[^"]+)"', block)
                title_m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', block, re.I | re.S)
                if not link_m or not title_m:
                    continue
                titulo = _strip_html(title_m.group(1))
                url = link_m.group(1)
                if url in seen or "category/" in url:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": None,
                        "url": url,
                        "blob": titulo,
                        "origen": "web_tablon",
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

    def _parse_wfs_member(self, member: ET.Element, ine: str, layer: str) -> dict[str, Any] | None:
        feat = None
        for child in member:
            tag = child.tag.split("}")[-1]
            if tag in (layer, "InventarioSuSuz", "Zonificacion"):
                feat = child
                break
        if feat is None:
            return None
        cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
        if cod != ine:
            return None
        fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
        pp = _strip_html(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
        ue = _strip_html(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
        denom = _strip_html(
            feat.findtext("ms:denominaci", default="", namespaces=_GML_NS)
            or feat.findtext("ms:denominaci_val", default="", namespaces=_GML_NS)
            or ""
        )
        clas = _strip_html(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Ámbito {fid}"
        geom = _gml_feature_to_geojson(feat)
        return {
            "titulo": titulo[:500],
            "fecha": f_aprob,
            "pp": pp,
            "ue": ue,
            "clasificacion": clas,
            "wfs_id": f"{layer}:{fid}",
            "geom": geom,
            "origen": "icv_wfs",
        }

    def _load_wfs_for_town(self, town: TownConfig) -> list[dict[str, Any]]:
        if town.ine in self._wfs_by_ine:
            return self._wfs_by_ine[town.ine]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"), (self.icv_layer_zon, "Zonificacion")):
            start = 0
            empty_pages = 0
            while start < 8000:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=90)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                page_hits = 0
                for member in members:
                    rec = self._parse_wfs_member(member, town.ine, layer)
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                        page_hits += 1
                if page_hits == 0:
                    empty_pages += 1
                    if empty_pages >= 8:
                        break
                else:
                    empty_pages = 0
                start += 200
        self._wfs_by_ine[town.ine] = rows
        index: dict[str, dict[str, Any]] = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    index[low] = rec
        self._wfs_index[town.ine] = index
        return rows

    def _match_wfs(self, town: TownConfig, text: str) -> dict[str, Any] | None:
        if town.ine not in self._wfs_index:
            self._load_wfs_for_town(town)
        index = self._wfs_index.get(town.ine, {})
        blob = (text or "").lower()
        for key, rec in index.items():
            if len(key) >= 4 and key in blob:
                return rec
        m = RE_SECTOR_CODE.search(text or "")
        if m:
            code = re.sub(r"\s+", " ", m.group(1).strip()).lower()
            for key, rec in index.items():
                if code in key:
                    return rec
        return None

    def _ensure_coords(self, town: TownConfig, rec: dict[str, Any]) -> None:
        if rec.get("lat") is not None and rec.get("lon") is not None:
            return
        rec["lat"] = town.centroid[0]
        rec["lon"] = town.centroid[1]
        rec.setdefault("coord_source", "municipio_centroid")

    def _attach_geometry(self, town: TownConfig, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        match = self._match_wfs(town, rec.get("titulo") or "")
        if not match or not match.get("geom"):
            self._ensure_coords(town, rec)
            return
        rec["geom_geojson"] = match["geom"]
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = self._wfs_page_url(self.icv_layer_su, 0)
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(match["geom"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_licencia_info_pages(self, town: TownConfig) -> list[dict[str, Any]]:
        pages = [
            {
                "id": _stable_id(town.id_prefix, "lic", town.board_url or town.tablon_rss or town.sede_base),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": town.centroid[0],
                "lon": town.centroid[1],
                "titulo": f"Tablón de anuncios — {town.municipio}",
                "url": town.board_url or town.tablon_rss or f"{town.sede_base}/tablondeanuncios/",
                "source": "ayuntamiento",
                "municipio": town.municipio,
                "nota": "Concesiones y edictos publicados en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id(town.id_prefix, "lic", f"{town.sede_base}/catalogo"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": town.centroid[0],
                "lon": town.centroid[1],
                "titulo": f"Catálogo de trámites — {town.municipio}",
                "url": (
                    f"{town.sede_base}/dossier"
                    if town.sede_kind == "espublico"
                    else f"{town.sede_base}/catalogoservicios.aspx"
                ),
                "source": "ayuntamiento",
                "municipio": town.municipio,
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
        ]
        return pages

    def _is_urban_blob(self, blob: str, procedimiento: str = "") -> bool:
        if RE_BOARD_NON_URBAN.search(blob):
            if not re.search(
                r"(?i)(pgou|planeam|urban|licencia|llic|obra|sector|suelo|informaci[oó]n p[uú]blica|concessi)",
                blob,
            ):
                return False
        proc = (procedimiento or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genérico", "general")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _rss_to_licencia(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban_blob(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec = {
            "id": _stable_id(town.id_prefix, "lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / actividad",
            "distrito": None,
            "lat": town.centroid[0],
            "lon": town.centroid[1],
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "municipio": town.municipio,
            "origen": row.get("origen") or "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _rss_to_proyecto(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        rec = {
            "id": _stable_id(town.id_prefix, "proy", row["url"]),
            "municipio": town.municipio,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _board_to_licencia(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob, row.get("procedimiento") or ""):
            return None
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
            "id": _stable_id(town.id_prefix, "lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": town.centroid[0],
            "lon": town.centroid[1],
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "municipio": town.municipio,
            "origen": "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _board_to_proyecto(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob, row.get("procedimiento") or ""):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "genérico" not in proc:
            if not any(k in (row.get("categoria") or "").lower() for k in ("urban", "planeam", "general")):
                return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id(town.id_prefix, "proy", key),
            "municipio": town.municipio,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _wfs_to_proyecto(self, town: TownConfig, item: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id(town.id_prefix, "proy", item["wfs_id"]),
            "municipio": town.municipio,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item.get("titulo") or ""),
            "url": (
                f"https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                f"#municipio={town.municipio}"
            ),
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "sector": item.get("pp"),
            "ue": item.get("ue"),
        }
        geom = item.get("geom")
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._wfs_page_url(self.icv_layer_su, 0)
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        else:
            self._ensure_coords(town, rec)
        return rec

    def _seed_to_proyecto(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob) and row.get("origen") != "web_seed":
            return None
        rec = {
            "id": _stable_id(town.id_prefix, "proy", row["url"]),
            "municipio": town.municipio,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_seed",
        }
        self._attach_geometry(town, rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for town in TOWNS:
            for rec in self._collect_licencia_info_pages(town):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
            for item in self._collect_tablon_rss(town):
                rec = self._rss_to_licencia(town, item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
            for item in self._collect_espublico_board(town):
                rec = self._board_to_licencia(town, item)
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
        stats = self.backfill_licencias(out_jsonl)
        rows = self._load_jsonl(out_jsonl)
        for r in rows:
            existing[r["id"]] = r
        merged = list(existing.values())
        self._write_jsonl(out_jsonl, merged)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(merged),
                    "added": max(0, len(merged) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(merged), "added": max(0, len(merged) - before), "status": "ok", **stats}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for town in TOWNS:
            for item in self._load_wfs_for_town(town):
                add(self._wfs_to_proyecto(town, item))
            for item in self._collect_seed_docs(town):
                add(self._seed_to_proyecto(town, item))
            for item in self._collect_tablon_rss(town):
                add(self._rss_to_proyecto(town, item))
            for item in self._collect_espublico_board(town):
                add(self._board_to_proyecto(town, item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
