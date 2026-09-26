from __future__ import annotations

import hashlib
import json
import re
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

WEB_BASE = "https://www.lalcudia.com"
WEB_JOOMLA = f"{WEB_BASE}/web"
MUNICIPIO = "L'Alcúdia"
ID_PREFIX = "lalcudia"
COD_INE_MUN = "46019"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "ms:Planeamiento.Zonificacion"
ICV_VISOR_URL = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

ICV_ZONES: list[dict[str, str]] = [
    {
        "fid": "889",
        "denominaci": "PROGRAMA DE ACTUACIÓN INTEGRADA Y PLAN PARCIAL DEL SECTOR S-15 (INDUSTRIAL)",
        "expediente": "20050623",
        "tipo": "plan parcial",
    },
    {
        "fid": "887",
        "denominaci": "Plan general",
        "expediente": "20000124",
        "tipo": "PGOU",
    },
]

SEED_ARTICLES = [116, 450, 460, 887, 980, 434]
TRAMITES_URL = f"{WEB_JOOMLA}/index.php?option=com_content&view=article&id=460"
PGOU_URL = f"{WEB_JOOMLA}/index.php?option=com_content&view=article&id=116"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|obra (?:major|menor)|parcelaci[oó]n|"
    r"ocupaci[oó]n via|devoluci[oó]n fiança)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|poum|pmus|puam|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|normas urban|ordenan|catalogo|cat[aà]leg|"
    r"homologaci[oó]n|programa.*actuaci|pai\b|registre.*urban|plantejament)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


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


def _fecha_from_path(path: str) -> str | None:
    m = re.search(r"/(\d{4})/(\d{2})(\d{2})_", path)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{2})(\d{2})(\d{2})_", Path(path).name)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000 if y < 50 else 1900
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(path) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "plan general" in n or "ordenaci" in n and "urbana" in n:
        return "PGOU"
    if "pmus" in n or "mobilitat" in n:
        return "plan movilidad urbana"
    if "puam" in n:
        return "plan urbano actuación municipal"
    if "plan parcial" in n or "sector" in n or "pai" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "reparcel" in n:
        return "reparcelación"
    if "registre" in n and "urban" in n:
        return "registro interés urbanístico"
    if "normas" in n or "normativa" in n:
        return "normativa urbanística"
    if "catalog" in n:
        return "catálogo protecciones"
    return "planeamiento"


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
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


class LalcudiaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla lalcudia.com (PGOU PDFs, trámites) + ICV WFS zonificación (partial). Sede GVA/sedipualba inactiva."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_JOOMLA)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.web_joomla = str(self.config.get("web_joomla") or WEB_JOOMLA).rstrip("/")
        self.seed_articles = [int(x) for x in (self.config.get("seed_articles") or SEED_ARTICLES)]
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lalcudia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lalcudia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href.split("&amp;", 1)[0]
        if href.startswith("/"):
            return f"{self.web_base}{href}"
        if href.startswith("../"):
            return urllib.parse.urljoin(f"{self.web_joomla}/", href)
        return urllib.parse.urljoin(f"{self.web_joomla}/", href)

    def _article_url(self, article_id: int) -> str:
        return (
            f"{self.web_joomla}/index.php?option=com_content&view=article&id={article_id}"
        )

    def _icv_geometry_url(self, fid: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.icv_type_name,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": "1",
                "featureId": f"Planeamiento.Zonificacion.{fid}",
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _fetch_icv_geometry(self, fid: str) -> dict[str, Any] | None:
        if fid in self._icv_geom_cache:
            cached = self._icv_geom_cache[fid]
            return dict(cached) if cached else None
        url = self._icv_geometry_url(fid)
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._icv_geom_cache[fid] = None
            return None
        feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
        if not feats:
            self._icv_geom_cache[fid] = None
            return None
        props = feats[0].get("properties") or {}
        if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
            self._icv_geom_cache[fid] = None
            return None
        merged = _merge_geometries([f.get("geometry") for f in feats if f.get("geometry")])
        if not merged:
            self._icv_geom_cache[fid] = None
            return None
        result = {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
            "icv_fid": fid,
        }
        self._icv_geom_cache[fid] = result
        return dict(result)

    def _match_icv_zone(self, titulo: str) -> dict[str, str] | None:
        norm = _normalize_title(titulo)
        best: tuple[float, dict[str, str]] | None = None
        for zone in ICV_ZONES:
            den = _normalize_title(zone["denominaci"])
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif "PGOU" in zone.get("tipo", "").upper() and re.search(
                r"(?i)pgou|plan general|ordenaci.*urbana|normas urban", titulo
            ):
                score = 80.0
            elif "sector" in norm and "sector" in den:
                score = 60.0
            elif "S-15" in norm and "S-15" in den:
                score = 90.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)
        if best and best[0] >= 30:
            return best[1]
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._fetch_icv_geometry(zone["fid"])
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_article_links(self, article_id: int) -> list[dict[str, str]]:
        try:
            html = self._fetch(self._article_url(article_id))
        except urllib.error.URLError:
            return []
        rows: list[dict[str, str]] = []
        for href, text in RE_LINK.findall(html):
            label = _strip_html(text)
            url = self._abs_url(href)
            if not label and ".pdf" not in url.lower():
                continue
            rows.append({"label": label, "url": url, "href": href})
        return rows

    def _collect_pdf_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for article_id in self.seed_articles:
            for link in self._collect_article_links(article_id):
                url = link["url"]
                if ".pdf" not in url.lower():
                    continue
                if url in seen:
                    continue
                label = link["label"] or Path(urllib.parse.unquote(url)).name
                blob = f"{label} {url}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(url)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": f"{MUNICIPIO}: {label}"[:500],
                    "fecha": _fecha_from_path(url),
                    "tipo": _proyecto_tipo(blob),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": f"joomla_art_{article_id}",
                }
                self._enrich_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for zone in ICV_ZONES:
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['fid']}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_path(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": ICV_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
                "icv_fid": zone["fid"],
            }
            geom = self._fetch_icv_geometry(zone["fid"])
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_forms(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for link in self._collect_article_links(460):
            url = link["url"]
            label = link["label"] or Path(urllib.parse.unquote(url)).name
            blob = f"{label} {url}"
            if ".pdf" not in url.lower() and "llicencies" not in url.lower():
                continue
            if not RE_LICENCIA.search(blob) and "llicencies" not in url.lower():
                continue
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _fecha_from_path(url),
                    "tipo": label[:200] or "formulario licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": label[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "joomla_tramites",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (formularios)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tràmits d'urbanisme — formularis licencias y DR",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Sede GVA 503 y sedipualba inactiva; formularios en web Joomla",
                "origen": "joomla_tramites",
            }
        )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_forms()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "origen": "joomla_tramites",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_icv_proyectos() + self._collect_pdf_proyectos():
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            rows.append(rec)
        rows.append(
            {
                "id": _stable_id("proy", self.pgou_url),
                "municipio": MUNICIPIO,
                "titulo": "Pla d'Ordenació Urbana (PGOU) — documentación municipal",
                "fecha": None,
                "tipo": "PGOU",
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "origen": "joomla_pgou",
            }
        )
        self._enrich_geometry(rows[-1])
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
