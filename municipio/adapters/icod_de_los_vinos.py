from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

WP_BASE = "https://icoddelosvinos.es"
SEDE_BASE = "https://sede.icoddelosvinos.es"
GEOBDP_BASE = "https://geobdp.grafcan.es/core"
MUNICIPIO = "Icod de los Vinos"
ID_PREFIX = "icod"
INE_MUNICIPIO = 38022

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
SITCAN_PACKAGE_URL = (
    "https://opendata.sitcan.es/api/3/action/package_show"
    "?id=planeamiento-urbanistico-de-icod-de-los-vinos"
)
WP_TRAMITE_API = f"{WP_BASE}/wp-json/wp/v2/tramite"

RE_LICENCIA = re.compile(
    r"(?i)(licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"certificado de viabilidad|cedula urban|c[eé]dula urban|segregaci[oó]n|parcelaci[oó]n|"
    r"pr[oó]rroga de licencia|comunicaci[oó]n subrogaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de detalle|ac[uú]stico)|memoria|planos|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"sector|suelo|normas subsidiarias|ordenanza(?:s)?(?: municipal(?:es)?)?(?: de)? edificaci[oó]n|"
    r"pmus|movilidad urbana|disoluci[oó]n.*urbanismo|calificaci[oó]n|suspensi[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|tribunal calificador|baremaci[oó]n|"
    r"padrones?\s+(?:ibi|del impuesto)|impuesto sobre (?:actividades|veh[ií]culos|construcciones)|"
    r"subvenci[oó]n|becas?|plan de emergencia|medalla|icodtesa|funcanorte|"
    r"ordenanza fiscal reguladora de la tasa por (?:servicio|prestaci[oó]n|recogida)|"
    r"huerto urbano municipal sostenible|protecci[oó]n del medio ambiente urbano contra la emisi[oó]n de ruidos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GEOM_JSON = re.compile(r"App\.Map\.zoomToExtent\((\{.*?\})\)\s*;", re.S)
RE_GEOBDP_DOC = re.compile(
    r'href="(?:/core)?/documentos/(\d+)\.html">([^<]+)',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_title(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


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


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pmus" in b or "movilidad urbana" in b:
        return "PMUS"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "ordenanza" in b and "edificaci" in b:
        return "ordenanza edificación"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    return "urbanismo"


def _utm28n_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    zone = 28
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    e = math.sqrt(2 * f - f * f)
    e1sq = e * e / (1 - e * e)
    x = easting - 500000.0
    y = northing
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))
    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = e1sq * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1 - e**2) / (1 - (e * math.sin(fp)) ** 2) ** 1.5
    n1 = a / math.sqrt(1 - (e * math.sin(fp)) ** 2)
    d = x / (n1 * k0)
    q1 = n1 * math.tan(fp) / r1
    q2 = d**2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e1sq) * d**4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e1sq - 3 * c1**2) * d**6 / 720
    lat = fp - q1 * (q2 - q3 + q4)
    q5 = d
    q6 = (1 + 2 * t1 + c1) * d**3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e1sq + 24 * t1**2) * d**5 / 120
    lon = lon0 + (q5 - q6 + q7) / math.cos(fp)
    return math.degrees(lat), math.degrees(lon)


def _reproject_coords(node: Any) -> Any:
    if isinstance(node, (list, tuple)):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            lat, lon = _utm28n_to_wgs84(float(node[0]), float(node[1]))
            return [lon, lat]
        return [_reproject_coords(item) for item in node]
    return node


def _feature_collection_to_geom(fc: dict[str, Any]) -> dict[str, Any] | None:
    feats = fc.get("features") or []
    if not feats:
        return None
    geoms = [f.get("geometry") for f in feats if isinstance(f, dict) and f.get("geometry")]
    if not geoms:
        return None
    if len(geoms) == 1:
        g = geoms[0]
        return {
            "type": g["type"],
            "coordinates": _reproject_coords(g["coordinates"]),
        }
    polys: list[Any] = []
    for g in geoms:
        gtype = g.get("type")
        coords = _reproject_coords(g.get("coordinates"))
        if gtype == "Polygon":
            polys.append(coords)
        elif gtype == "MultiPolygon":
            polys.extend(coords)
    if not polys:
        return None
    return {"type": "MultiPolygon", "coordinates": polys}


class IcodDeLosVinosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress trámites + sede STA tablón + SITCAN planeamiento + GEOBDP geometría."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.ine_municipio = int(self.config.get("geobdp_municipio") or INE_MUNICIPIO)
        self._geobdp_docs: dict[int, str] = {}
        self._geom_cache: dict[int, dict[str, Any]] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-icod-de-los-vinos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_wp_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{WP_TRAMITE_API}?per_page=100&page={page}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            for item in data:
                title = unescape(str((item.get("title") or {}).get("rendered") or "")).strip()
                link = str(item.get("link") or "")
                slug = str(item.get("slug") or link)
                fecha = str(item.get("modified") or "")[:10] or None
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "slug": slug,
                        "origen": "wordpress_tramite",
                    }
                )
            if len(data) < 100:
                break
            page += 1
        return rows

    def _collect_sitcan_planeamiento(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            payload = self._fetch_json(SITCAN_PACKAGE_URL)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return rows
        resources = (payload.get("result") or {}).get("resources") or []
        for res in resources:
            desc = str(res.get("description") or res.get("name") or "").strip()
            if not desc or desc in seen:
                continue
            fmt = str(res.get("format") or "").upper()
            if fmt not in {"PDF", "HTML", "SIPU"}:
                continue
            if not RE_PROYECTO.search(desc):
                continue
            seen.add(desc)
            url = str(res.get("url") or "")
            rows.append(
                {
                    "titulo": desc[:500],
                    "fecha": _fecha_from_blob(desc),
                    "url": url or f"https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-icod-de-los-vinos",
                    "origen": "sitcan_ckan",
                    "formato": fmt,
                }
            )
        return rows

    def _load_geobdp_catalog(self) -> dict[int, str]:
        if self._geobdp_docs:
            return self._geobdp_docs
        url = f"{GEOBDP_BASE}/municipios/{self.ine_municipio}/"
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return {}
        for m in RE_GEOBDP_DOC.finditer(html):
            doc_id = int(m.group(1))
            title = unescape(re.sub(r"\s+", " ", m.group(2))).strip()
            title = re.sub(r"\s*\(\d+\)\s*$", "", title)
            self._geobdp_docs[doc_id] = title
        return self._geobdp_docs

    def _fetch_geobdp_geometry(self, doc_id: int) -> dict[str, Any] | None:
        if doc_id in self._geom_cache:
            return self._geom_cache[doc_id]
        url = f"{GEOBDP_BASE}/documentos/{doc_id}.html"
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        m = RE_GEOM_JSON.search(html)
        if not m:
            return None
        try:
            fc = json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
        geom = _feature_collection_to_geom(fc)
        if not geom:
            return None
        entry = {
            "geom_geojson": geom,
            "geometry_source": "portal_geobdp_grafcan",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
            "geobdp_doc_id": doc_id,
        }
        self._geom_cache[doc_id] = entry
        return entry

    def _match_geometry(self, titulo: str) -> dict[str, Any] | None:
        catalog = self._load_geobdp_catalog()
        if not catalog:
            return None
        norm = _norm_title(titulo)
        if not norm:
            return None
        best_id: int | None = None
        best_score = 0
        norm_tokens = set(norm.split())
        for doc_id, doc_title in catalog.items():
            doc_norm = _norm_title(doc_title)
            if not doc_norm:
                continue
            if doc_norm in norm or norm in doc_norm:
                score = max(len(doc_norm), len(norm))
            else:
                doc_tokens = set(doc_norm.split())
                score = len(norm_tokens & doc_tokens)
            if score > best_score:
                best_score = score
                best_id = doc_id
        if best_id is None or best_score < 4:
            return None
        return self._fetch_geobdp_geometry(best_id)

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if rec.get("geom_geojson"):
            return
        geom = self._match_geometry(rec.get("titulo", ""))
        if not geom:
            return
        rec.update(geom)
        cen = geometry_centroid(rec["geom_geojson"])
        if cen:
            rec["lat"], rec["lon"] = cen

    def _tablon_to_record(self, row: dict[str, Any]) -> tuple[str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, fecha, url

    def _to_licencia_tramite(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        if RE_EXCLUDE.search(titulo):
            return None
        url = row["url"]
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite informativo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_licencia_tablon(self, title: str, fecha: str, url: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        if RE_EXCLUDE.search(title):
            return None
        if RE_PROYECTO.search(title) and "licencia" not in title.lower():
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia / anuncio",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": "sta_tablon",
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('origen', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
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
        raw: list[dict[str, Any]] = []
        for row in self._collect_wp_tramites():
            lic = self._to_licencia_tramite(row)
            if lic:
                raw.append(lic)
        for item in self._collect_tablon():
            title, fecha, url = self._tablon_to_record(item)
            lic = self._to_licencia_tablon(title, fecha, url)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wordpress_sta"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": max(0, result["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_sitcan_planeamiento():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        catalog = self._load_geobdp_catalog()
        for doc_id, title in catalog.items():
            proy = self._to_proyecto(
                {
                    "titulo": title,
                    "fecha": _fecha_from_blob(title),
                    "url": f"{GEOBDP_BASE}/documentos/{doc_id}.html",
                    "origen": "geobdp_catalog",
                }
            )
            if proy:
                geom = self._fetch_geobdp_geometry(doc_id)
                if geom:
                    proy.update(geom)
                    cen = geometry_centroid(proy["geom_geojson"])
                    if cen:
                        proy["lat"], proy["lon"] = cen
                raw.append(proy)
        for item in self._collect_tablon():
            title, fecha, url = self._tablon_to_record(item)
            proy = self._to_proyecto(
                {
                    "titulo": title,
                    "fecha": fecha or None,
                    "url": url,
                    "origen": "sta_tablon",
                }
            )
            if proy:
                raw.append(proy)
        seed_pages = [
            f"{WP_BASE}/planteamiento-urbanistico/",
            f"{WP_BASE}/ayuntamiento/tramites/?tipo=urbanismo",
        ]
        for page_url in seed_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            title_m = re.search(r"<title[^>]*>([^<]+)", html)
            page_title = unescape(title_m.group(1).strip()) if title_m else page_url
            proy = self._to_proyecto(
                {
                    "titulo": page_title[:500],
                    "fecha": None,
                    "url": page_url,
                    "origen": "wordpress_page",
                }
            )
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "geobdp_docs": len(catalog),
            "sitcan": len(self._collect_sitcan_planeamiento()),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": max(0, result["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
