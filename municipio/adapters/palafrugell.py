from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely import wkt as shapely_wkt
from shapely.ops import transform as shapely_transform

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

WEB_BASE = "https://palafrugell.cat"
MAPES_BASE = "https://mapes.palafrugell.cat"
SEU_BASE = "https://seu.palafrugell.cat"
MUNICIPIO = "Palafrugell"
ID_PREFIX = "palafrugell"

EXPEDIENTS_ROOT = (
    f"{WEB_BASE}/serveis-ciutadania/urbanisme/expedients-urbanistics-en-tramitacio"
)
GEOPORTAL_URL = f"{MAPES_BASE}/geoportal/"
SUGGEST_BASE = f"{MAPES_BASE}/cercagis_suggest/simple/all"
TAULER_URL = "https://tauler.seu.cat/inici.do?idens=1711750006"

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{SEU_BASE}/tramits/urbanisme-i-obres",
        "Tràmits urbanisme i obres (seu electrònica)",
    ),
    (
        f"{WEB_BASE}/serveis-ciutadania/urbanisme/tramitacio-de-llicencies",
        "Tramitació de llicències — informació",
    ),
    (TAULER_URL, "e-TAULER — anuncis i edictes (exposició pública)"),
    (
        f"{SEU_BASE}/informacio-municipal/expedients-en-informacio-publica",
        "Expedients en informació pública (seu)",
    ),
]

RE_LISTING_ITEM = re.compile(
    r"<h2[^>]*>(.*?)</h2>\s*<ul[^>]*>.*?"
    r'href="(https://mapes\.palafrugell\.cat[^"]+)"',
    re.I | re.S,
)
RE_PAGE_LINK = re.compile(
    r'href="(/serveis-ciutadania/urbanisme/expedients-urbanistics-en-tramitacio/\d+)"',
    re.I,
)
RE_PLANEJAMENT_CODE = re.compile(
    r"/Planejament(?:Derivat)?/[^/]+/[A-Z]/([A-Z]\d+)/",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|comunicaci[oó] pr[eè]via|declaraci[oó] responsable|"
    r"obra (?:major|menor)|enderroc|r[eè]tol)",
)

_TRANSFORMER_25831_TO_4326 = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _fecha_from_blob(text: str) -> str | None:
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "poum" in n or "pla general" in n or "pgou" in n:
        return "POUM / planeamiento general"
    if "pla especial" in n or " pe " in f" {n} " or "peu " in n or "pepiphp" in n:
        return "plan especial"
    if "pla de millora" in n or "pmu" in n or " pau " in f" {n} ":
        return "plan de mejora urbana"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual POUM"
    if "reparcel" in n:
        return "reparcelación"
    if "urbanitzaci" in n or "urbanizaci" in n:
        return "urbanización"
    if "suspensi" in n:
        return "suspensión licencias"
    if "conveni" in n:
        return "convenio urbanístico"
    if "projecte" in n or "proyecto" in n:
        return "proyecto urbanístico"
    if "llic" in n:
        return "licencia / actividad"
    if "espectacle" in n or "festival" in n:
        return "actividad / evento"
    return "planeamiento urbanístico"


def _normalize_tokens(text: str) -> set[str]:
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    stop = {
        "de",
        "del",
        "la",
        "el",
        "les",
        "els",
        "a",
        "al",
        "en",
        "per",
        "i",
        "n",
        "num",
        "núm",
        "palafrugell",
        "calella",
        "tamariu",
        "llafranc",
        "llofriu",
    }
    return {w for w in t.split() if len(w) > 2 and w not in stop}


def _score_suggest_match(titulo: str, candidate: dict[str, Any]) -> float:
    label = str(candidate.get("label") or candidate.get("text") or "")
    ctoks = _normalize_tokens(label)
    ttoks = _normalize_tokens(titulo)
    if not ctoks or not ttoks:
        return 0.0
    inter = len(ctoks & ttoks)
    return inter / max(len(ttoks), 1)


def _wkt_polygon_to_wgs84_geojson(wkt_str: str) -> dict[str, Any] | None:
    if not wkt_str or not wkt_str.strip().upper().startswith("POLYGON"):
        return None
    try:
        geom = shapely_wkt.loads(wkt_str)
    except Exception:
        return None

    def _proj(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return _TRANSFORMER_25831_TO_4326.transform(x, y)

    g4326 = shapely_transform(_proj, geom)
    if g4326.is_empty:
        return None
    out = json.loads(json.dumps(g4326.__geo_interface__))
    if out.get("type") not in {"Polygon", "MultiPolygon"}:
        return None
    return out


class PalafrugellAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla/ZOO (palafrugell.cat) + fitxes mapes.palafrugell.cat + geoportal NexusGIS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.expedients_root = str(self.config.get("expedients_root") or EXPEDIENTS_ROOT)
        self.suggest_base = str(self.config.get("suggest_base") or SUGGEST_BASE)
        self.licencia_pages = [
            tuple(x) for x in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.fetch_geometry = bool(self.config.get("fetch_geometry", True))
        self.geometry_min_score = float(self.config.get("geometry_min_score", 0.25))
        self.ua = str(self.config.get("user_agent", "poc-bocm-palafrugell/1.0"))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _listing_page_urls(self) -> list[str]:
        try:
            html = self._fetch(self.expedients_root)
        except (urllib.error.URLError, TimeoutError, OSError):
            return [self.expedients_root]
        pages = {self.expedients_root.rstrip("/")}
        for href in RE_PAGE_LINK.findall(html):
            pages.add(f"{self.web_base}{href.split('?')[0].rstrip('/')}")
        return sorted(pages)

    def _parse_listing(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for titulo_raw, fitxa_url in RE_LISTING_ITEM.findall(html):
            titulo = _strip_html(titulo_raw)[:500]
            if len(titulo) < 8:
                continue
            fitxa = unescape(fitxa_url.split("#")[0])
            code_m = RE_PLANEJAMENT_CODE.search(fitxa)
            planejament_code = code_m.group(1).upper() if code_m else None
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"{fitxa}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(titulo),
                "tipo": _proyecto_tipo(titulo),
                "url": fitxa,
                "source": "ayuntamiento",
                "origen": "expedients_tramitacio",
                "page_url": page_url,
            }
            if planejament_code:
                rec["planejament_code"] = planejament_code
            rows.append(rec)
        return rows

    def _fetch_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        titulo = str(rec.get("titulo") or "")
        query = titulo[:120].strip()
        if len(query) < 6:
            return rec
        url = f"{self.suggest_base}/{urllib.parse.quote(query, safe='')}"
        try:
            payload = self._fetch_json(url)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return rec
        candidates = [
            c
            for c in (payload.get("data") or [])
            if isinstance(c, dict) and str(c.get("category") or "") == "Planejament Derivat"
        ]
        if not candidates:
            return rec
        best = max(candidates, key=lambda c: _score_suggest_match(titulo, c))
        if _score_suggest_match(titulo, best) < self.geometry_min_score:
            return rec
        bbox_wkt = str(best.get("bbox") or "")
        geom = _wkt_polygon_to_wgs84_geojson(bbox_wkt)
        if not geom:
            return rec
        suggest_url = url
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["source_crs"] = "EPSG:4326"
        rec["coordinates_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_gis_suggest"
        rec["geometry_source_url"] = suggest_url
        rec["coord_source"] = "portal_geometry_centroid"
        rec["geometry_label"] = str(best.get("label") or "")[:300]
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for page in self._listing_page_urls():
            try:
                html = self._fetch(page)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for rec in self._parse_listing(html, page):
                if self.fetch_geometry:
                    rec = self._fetch_geometry(rec)
                by_id[rec["id"]] = rec
        geoportal = {
            "id": _stable_id("proy", GEOPORTAL_URL),
            "municipio": MUNICIPIO,
            "titulo": "Geoportal urbanístic municipal (mapes.palafrugell.cat)",
            "fecha": None,
            "tipo": "referencia cartográfica",
            "url": GEOPORTAL_URL,
            "source": "ayuntamiento",
            "origen": "geoportal_ref",
        }
        by_id.setdefault(geoportal["id"], geoportal)
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, label in self.licencia_pages:
            if page_url in seen:
                continue
            seen.add(page_url)
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": label[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        try:
            html = self._fetch(f"{SEU_BASE}/tramits/urbanisme-i-obres")
        except (urllib.error.URLError, TimeoutError, OSError):
            html = ""
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
            href, inner = m.group(1), m.group(2)
            titulo = _strip_html(inner)
            if not RE_LICENCIA.search(titulo):
                continue
            u = urllib.parse.urljoin(f"{SEU_BASE}/", unescape(href))
            if u in seen or "seu.palafrugell" not in u:
                continue
            seen.add(u)
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": None,
                    "tipo": titulo[:200] or "Tràmit urbanisme",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "seu_tramits",
                }
            )
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["with_geometry"] = sum(1 for r in rows if r.get("geom_geojson"))
        return meta

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        return self._write_jsonl(out_jsonl, rows)

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
