from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

SITCAN_DATASET = "planeamiento-urbanistico-de-los-llanos-de-aridane"
SITCAN_URL = f"https://opendata.sitcan.es/dataset/{SITCAN_DATASET}"
GEOBDP_MUNICIPIO = "https://geobdp.grafcan.es/core/municipios/38024/"
SEDE_BASE = "https://losllanosdearidane.sedelectronica.es"
MUNICIPIO = "Los Llanos de Aridane"
ID_PREFIX = "lla"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"obra (?:mayor|menor)|licencia apertura|actividad (?:inocua|clasificada|minorista)|alineaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|sapur|susno|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|sentencia|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|suelo|"
    r"cambio de uso|ordenanza|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|instrumento|urbanizaci[oó]n|pamu|revisi[oó]n|suspendid|"
    r"volc[aá]nic|erupci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GEOBDP_DOC = re.compile(
    r'href="/core/documentos/(\d+)\.html">([^<]+)',
    re.I,
)
RE_GEOBDP_ZOOM = re.compile(r"App\.Map\.zoomToExtent\((\{.*?\})\);", re.S)
RE_GEOBDP_URL = re.compile(r"https?://geobdp\.grafcan\.es/core/documentos/(\d+)")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "sentencia" in b:
        return "sentencia judicial"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza"
    if "modificaci" in b:
        return "modificación puntual"
    if "suspendid" in b:
        return "ámbito suspendido"
    if "revisi" in b:
        return "revisión"
    if "volc" in b or "erupci" in b:
        return "ordenanza post-volcánica"
    return "urbanismo"


def _utm28n_to_lonlat(x: float, y: float) -> tuple[float, float]:
    k0 = 0.9996
    a = 6378137.0
    e = 0.081819191
    e2 = e * e
    e4 = e2 * e2
    e6 = e4 * e2
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    lon0 = math.radians(-15.0)
    x = x - 500000.0
    m_val = y / k0
    mu = m_val / (a * (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256))
    phi1 = mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
    phi1 += (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
    phi1 += (151 * e1**3 / 96) * math.sin(6 * mu)
    phi1 += (1097 * e1**4 / 512) * math.sin(8 * mu)
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = e2 * math.cos(phi1) ** 2 / (1 - e2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d_val = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d_val**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e2) * d_val**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e2 - 3 * c1**2) * d_val**6 / 720
    )
    lon = lon0 + (
        d_val
        - (1 + 2 * t1 + c1) * d_val**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e2 + 24 * t1**2) * d_val**5 / 120
    ) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def _transform_coord_pair(pair: list[float] | tuple[float, float]) -> list[float]:
    lon, lat = _utm28n_to_lonlat(float(pair[0]), float(pair[1]))
    return [lon, lat]


def _transform_coords(node: Any) -> Any:
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            if len(node) == 2 or (len(node) > 2 and not isinstance(node[2], (list, tuple))):
                return _transform_coord_pair(node)
        return [_transform_coords(item) for item in node]
    return node


def _wgs84_geometry(geom: dict[str, Any]) -> dict[str, Any]:
    return {"type": geom.get("type"), "coordinates": _transform_coords(geom.get("coordinates"))}


class LosLlanosDeAridaneAyuntamientoAdapter(AyuntamientoAdapter):
    """SITCAN/IDE Canarias + GEOBDP Grafcan (web municipal y sede indeterminadas)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SITCAN_URL)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.geobdp_municipio = str(self.config.get("geobdp_municipio") or GEOBDP_MUNICIPIO)
        self.sitcan_dataset = str(self.config.get("sitcan_dataset") or SITCAN_DATASET)
        self._geom_cache: dict[str, dict[str, Any] | None] = {}
        self._geobdp_index: dict[str, str] | None = None

    def _fetch(self, url: str, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-llanos-de-aridane/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode(encoding, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-llanos-de-aridane/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _geobdp_geometry(self, url: str) -> dict[str, Any] | None:
        if url in self._geom_cache:
            return self._geom_cache[url]
        geom: dict[str, Any] | None = None
        if "geobdp.grafcan.es" not in url:
            self._geom_cache[url] = None
            return None
        fetch_url = url if url.endswith("/") else f"{url}/"
        if fetch_url.endswith(".html/"):
            fetch_url = fetch_url.replace(".html/", ".html")
        try:
            html = self._fetch(fetch_url)
        except urllib.error.URLError:
            self._geom_cache[url] = None
            return None
        m = RE_GEOBDP_ZOOM.search(html)
        if not m:
            self._geom_cache[url] = None
            return None
        try:
            fc = json.loads(m.group(1))
            feats = fc.get("features") or []
            if feats and isinstance(feats[0], dict):
                raw_geom = feats[0].get("geometry")
                if isinstance(raw_geom, dict) and raw_geom.get("coordinates"):
                    crs_name = str((fc.get("crs") or {}).get("properties", {}).get("name", ""))
                    if "32628" in crs_name:
                        geom = _wgs84_geometry(raw_geom)
                    else:
                        geom = raw_geom
        except (json.JSONDecodeError, TypeError, ValueError):
            geom = None
        self._geom_cache[url] = geom
        return geom

    def _attach_geometry(self, rec: dict[str, Any], source_url: str) -> None:
        geobdp_url = rec.get("geobdp_url") or ""
        if not geobdp_url and "geobdp.grafcan.es" in source_url:
            geobdp_url = source_url
        if not geobdp_url:
            return
        geom = self._geobdp_geometry(geobdp_url)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_geobdp_grafcan"
        rec["geometry_source_url"] = geobdp_url
        rec["coord_source"] = "portal_geometry_centroid"

    def _load_geobdp_index(self) -> dict[str, str]:
        if self._geobdp_index is not None:
            return self._geobdp_index
        index: dict[str, str] = {}
        try:
            html = self._fetch(self.geobdp_municipio)
        except urllib.error.URLError:
            self._geobdp_index = index
            return index
        for m in RE_GEOBDP_DOC.finditer(html):
            doc_id, title = m.group(1), _strip_html(m.group(2))
            index[title.lower()] = f"https://geobdp.grafcan.es/core/documentos/{doc_id}/"
        self._geobdp_index = index
        return index

    def _collect_sitcan(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(
                f"https://opendata.sitcan.es/api/3/action/package_show?id={self.sitcan_dataset}"
            )
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        result = data.get("result") or {}
        seen_titles: set[str] = set()
        for res in result.get("resources") or []:
            name = str(res.get("name") or "").strip()
            desc = str(res.get("description") or "")
            fmt = str(res.get("format") or "")
            url = str(res.get("url") or "").strip()
            if not name:
                continue
            blob = f"{name} {desc}"
            if not RE_PROYECTO.search(blob):
                continue
            norm_title = name.lower()
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)
            fecha = _fecha_from_blob(desc) or _fecha_from_blob(name)
            geobdp_url = url if "geobdp.grafcan.es" in url else ""
            if not geobdp_url:
                for candidate in (url, desc):
                    m = RE_GEOBDP_URL.search(candidate or "")
                    if m:
                        geobdp_url = f"https://geobdp.grafcan.es/core/documentos/{m.group(1)}/"
                        break
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": fecha,
                    "url": url or SITCAN_URL,
                    "blob": blob,
                    "origen": "sitcan",
                    "formato": fmt,
                    "geobdp_url": geobdp_url,
                }
            )
        return rows

    def _collect_geobdp_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        index = self._load_geobdp_index()
        for title, geobdp_url in index.items():
            blob = title
            if not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(title),
                    "url": geobdp_url,
                    "blob": blob,
                    "origen": "geobdp_catalog",
                    "formato": "HTML",
                    "geobdp_url": geobdp_url,
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        info_pages = [
            (self.sede_base, "Sede electrónica — Los Llanos de Aridane"),
            (f"{self.sede_base}/board", "Tablón de anuncios — sede electrónica"),
            (SITCAN_URL, "Planeamiento urbanístico — SITCAN Open Data"),
            (self.geobdp_municipio, "BDP planeamiento — GEOBDP Grafcan"),
            (
                "https://www.idecanarias.es/",
                "IDE Canarias — visor planeamiento",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in info_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("geobdp_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("geobdp_url") or row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("formato"):
            rec["formato"] = row["formato"]
        self._attach_geometry(rec, row.get("geobdp_url") or row.get("url") or "")
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._dedupe(self._collect_licencia_tramites())
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sitcan_informativo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_sitcan():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_geobdp_catalog():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "sitcan_geobdp",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
