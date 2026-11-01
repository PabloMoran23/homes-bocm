from __future__ import annotations

import hashlib
import http.client
import json
import re
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

WEB_BASE = "https://www.alaquas.org"
SEDE_BASE = "https://alaquas.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISME_SEDE = f"{SEDE_BASE}/citizen-service/ddd2e6a6-94d6-43c8-8c4b-661d76dbe3d6"
MUNICIPIO = "Alaquàs"
ID_PREFIX = "alaquas"
INE_MUN = "46004"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

DEFAULT_URBANISMO_SEEDS: list[dict[str, str]] = [
    {"url": f"{WEB_BASE}/monografies/pgou2015/", "titulo": "PGOU 2015 Alaquàs"},
    {"url": f"{WEB_BASE}/monografies/urbanismo-documento_mod2pgou/", "titulo": "Modificación puntual PGOU 2"},
    {"url": f"{WEB_BASE}/monografies/urbanismo-documento_mod3pgou/", "titulo": "Modificación puntual PGOU 3"},
    {"url": f"{WEB_BASE}/monografies/urbanismo-sector6/", "titulo": "Plan parcial Sector VI"},
    {"url": f"{WEB_BASE}/monografies/urbanismo-sector7/", "titulo": "Plan parcial Sector VII"},
    {"url": f"{WEB_BASE}/documento/17794?i=1", "titulo": "Plan urbano de actuación municipal (PUAM)"},
    {"url": f"{WEB_BASE}/documento/17508?i=1", "titulo": "Plan de movilidad sostenible"},
    {"url": f"{WEB_BASE}/ajuntament/1/", "titulo": "Documentación urbanística — ayuntamiento"},
]

RE_PREVIEW = re.compile(
    r'href="((?:https://alaquas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|vado|zanja|ocupaci[oó]n de v[ií]a|certificat.*urban|"
    r"informe urban|certificado urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|puam|sector|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|edicto|ordenanza|"
    r"certificat.*urban|informe urban|barranco|movilidad|sostenible)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(selecci[oó]n de personal|convocatoria.*empleo|subvenci[oó]n|personal|"
    r"objetos perdidos|veh[ií]culos abandonados|servicios sociales|iae\b|"
    r"impuesto sobre bienes inmuebles|ibi\b|tag urbanismo.*oposici|acción inserta|"
    r"escuela taller|familia numerosa|animales de compa)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|SECTOR)[\s\-]?(?:VI|VII|\d+|[\dA-ZÁÉÍÓÚ'._\-]+))\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DATA_LABEL = re.compile(r'data-label="([^"]+)"[^>]*>(.*?)</td>', re.I | re.S)

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}

_LABEL_MAP = {
    "document": "documento",
    "documento": "documento",
    "expedient": "expediente",
    "expediente": "expediente",
    "procediment": "procedimiento",
    "procedimiento": "procedimiento",
    "categoria": "categoria",
    "categoría": "categoria",
    "descripció": "descripcion",
    "descripción": "descripcion",
    "descripcion": "descripcion",
    "data de publicació": "fecha",
    "fecha de publicación": "fecha",
    "fecha de publicacion": "fecha",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "sector" in n:
        return "plan parcial / sector"
    if "mod" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "puam" in n:
        return "PUAM"
    if "ordenanza" in n:
        return "ordenanza"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "certificat" in n or "informe urban" in n:
        return "certificado / informe urbanístico"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    parts = [float(x) for x in poslist.split() if x.strip()]
    if len(parts) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(parts) - 1, 2):
        lat, lon = parts[i], parts[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    pos = feat.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class AlaquasAyuntamientoAdapter(AyuntamientoAdapter):
    """Web alaquas.org + sede espublico gestiona (tablón) + ICV WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_seeds = list(self.config.get("urbanismo_seeds") or DEFAULT_URBANISMO_SEEDS)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("layer_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("layer_zon") or ICV_LAYER_ZON)
        self.cod_ine_mun = str(geom_cfg.get("ine_municipio") or INE_MUN)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alaquas/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                for enc in ("utf-8", "latin-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError, http.client.IncompleteRead) as exc:
                last_err = exc
                time.sleep(0.6 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

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

    def _normalize_cells(self, row_html: str) -> dict[str, str]:
        cells: dict[str, str] = {}
        for label_m in RE_DATA_LABEL.finditer(row_html):
            raw_label = label_m.group(1).strip().lower()
            key = _LABEL_MAP.get(raw_label, raw_label)
            cells[key] = _strip_html(label_m.group(2))
        return cells

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells = self._normalize_cells(row_html)
            if not cells:
                continue
            documento = cells.get("documento", "")
            if documento.lower() in ("document", "documento", ""):
                continue
            preview_m = RE_PREVIEW.search(row_html)
            url = (
                urllib.parse.urljoin(f"{self.sede_base}/", preview_m.group(1))
                if preview_m
                else self.board_url
            )
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            descripcion = cells.get("descripcion", "")
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
            expediente = cells.get("expediente", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"
            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("procedimiento", "")[:200],
                    "categoria": cells.get("categoria", "")[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(cells.get("fecha", "")),
                    "url": url,
                    "pdf_url": url if "preview-document" in url else None,
                    "blob": " ".join(
                        str(cells.get(k) or "") for k in ("documento", "expediente", "procedimiento", "categoria", "descripcion")
                    ),
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_urbanismo_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.urbanismo_seeds:
            url = str(item["url"])
            titulo = str(item.get("titulo") or url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "origen": "web_urbanismo",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Alaquàs",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas (espublico gestiona)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", URBANISME_SEDE),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanisme i Activitats — sede electrónica",
                "url": URBANISME_SEDE,
                "source": "ayuntamiento",
                "nota": "Licencias, ocupación vía pública y seguimiento de obras",
                "origen": "sede_urbanisme",
            },
            {
                "id": _stable_id("lic", f"{WEB_BASE}/oac/menu.asp?i=1"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites OAC",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — licencias de obras y vía pública (OAC)",
                "url": f"{WEB_BASE}/oac/menu.asp?i=1",
                "source": "ayuntamiento",
                "nota": "Formularios: licencia obras, vados, zanjas, ocupación mesas",
                "origen": "oac_tramites",
            },
        ]

    def _wfs_page_url(self, type_name: str, start: int) -> str:
        cql = f"cod_ine_mun='{self.cod_ine_mun}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": "80",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
                "CQL_FILTER": cql,
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
        cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
        if cod != self.cod_ine_mun:
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
        exp = _strip_html(feat.findtext("ms:expediente", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue or f"Sector {fid}"
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        geom = _gml_feature_to_geojson(feat)
        url_abs = feat.findtext("ms:url_abs", default="", namespaces=_GML_NS) or VISOR_GVA
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob or _parse_fecha_dmy(exp),
            "url": url_abs,
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "pp": pp or None,
            "ue": ue or None,
            "expediente": exp or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_axis_order"] = "xy"
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._wfs_page_url(self.icv_layer_su, 0)
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"), (self.icv_layer_zon, "Zonificacion")):
            start = 0
            while start < 2000:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=90)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                matched = 0
                for member in members:
                    rec = self._parse_wfs_member(member, layer=layer.split(".")[-1])
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                        matched += 1
                if matched == 0 and start > 0:
                    break
                start += 200
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or "", rec.get("expediente") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for m in RE_SECTOR_TOKEN.finditer(rec.get("titulo") or ""):
                self._wfs_by_key[m.group(1).lower()] = rec
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
        for m in RE_SECTOR_TOKEN.finditer(text or ""):
            hit = (self._wfs_by_key or {}).get(m.group(1).lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "documento", "pp", "ue", "expediente", "blob"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_crs", "geometry_axis_order", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _wfs_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["wfs_id"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "planeamiento",
            "url": row.get("url") or VISOR_GVA,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in ("geom_geojson", "geometry_crs", "geometry_axis_order", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if row.get(key) is not None:
                rec[key] = row[key]
        return rec

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
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_urbanisme", "oac_tramites")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_urbanismo_seeds():
            add(self._seed_to_proyecto(item))
        for item in self._collect_icv_wfs():
            add(self._wfs_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "web_urbanismo": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
