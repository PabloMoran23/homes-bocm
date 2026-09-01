from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://aytosagunto.es"
SEDE = "https://sagunt.sedipualba.es"
MUNICIPIO = "Sagunt"
ID_PREFIX = "sagunt"
INE_MUN = "46220"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx"
CATALOGO_URBANISMO = f"{SEDE}/catalogoservicios.aspx?area=1260&ambito=1"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/pgou/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/revision-plan-general-municipal/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/convenios/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/documentacion-pormenorizada-vigente/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/instalacion-de-placas-fotovoltaicas/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/red-urbana-de-referencias-topograficas/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/2258025x-plan-especial-l-alqueria-d-aigua-freda/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/395008y-pri-pla-de-reforma-interior-n-2-monte-picayo/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/614057h-pepchas-pepaus-1-plan-especial-proteccion-conjunto-historico-artistico-e04-95pl/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/174648r-pai-agrupacion-de-interes-urbanistico-poligono-la-vila/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/1835492w-modificacion-previsiones-pgou-e-instrumentos-desarrollo-referentes-a-ordenacion-pormenorizada-distintos-ambitos/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/2082064f-sges-24-modificacion-de-previsiones-del-pgou/",
    f"{BASE}/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/2175107h-previsiones-sobre-las-viviendas-de-uso-turistico-en-sagunto/",
]

RE_UMBRACO_LINK = re.compile(
    r'href="(/es/ayuntamiento/areas-y-servicios/urbanismo[^"#?]+)"',
    re.I,
)
RE_TRAMITE = re.compile(
    r'href="(https://sagunt\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"\s*([^<]+)",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor)|autoritzaci[oó]|compatibilidad urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pri|peri|pai|"
    r"informaci[oó]n p[uú]blica|expedient|expropi|projecte|modificaci[oó]n|"
    r"estudi(?:s)? (?:de )?detall|reparcel|conveni|sector|ue-|pol[ií]gono|"
    r"participaci[oó]|reforma interior|urbanitz|ordenaci[oó]n|pepchas|pepaus|"
    r"estrat[eé]gic|vivienda[s]? (?:de )?uso tur[ií]stic)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|igualtat|cultural|festiu|ve[iï]nal|musical|empadron|"
    r"compte general|matr[ií]cula iae|borsa de treball|cessi[oó] d.us|pleno|"
    r"convocatoria.*pleno|edicto.*recaudat|peis|agricultura|cooperaci[oó]n internacional)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|PE|PAI|POL|RES)[\s\-]?(?:IND\s*)?[\dA-Z]+(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "expropi" in n:
        return "expropiación"
    if "plan especial" in n or "peri" in n or "pri" in n or "pepchas" in n:
        return "plan especial"
    if "plan parcial" in n or "pp " in n:
        return "plan parcial"
    if "estudi" in n and "detall" in n:
        return "estudio de detalle"
    if "participaci" in n:
        return "participación pública"
    if "informaci" in n:
        return "información pública"
    if "pgou" in n or "pla general" in n or "plan general" in n:
        return "plan general"
    if "pai" in n:
        return "agrupación de interés urbanístico"
    if "conveni" in n:
        return "convenio urbanístico"
    if re.search(r"\b(sd|ue|sector|pol[ií]gono)\b", n):
        return "sector planeamiento"
    if "ordenanza" in n:
        return "ordenanza urbanística"
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


class SaguntAyuntamientoAdapter(AyuntamientoAdapter):
    """Umbraco (aytosagunto.es) + sede sedipualba + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 60))
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sagunt/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*[-|].*Sagunt.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for catalog_url in (CATALOGO_URBANISMO, CATALOGO_TRAMITES):
            try:
                html = self._fetch(catalog_url)
            except urllib.error.URLError:
                continue
            for href, title in RE_TRAMITE.findall(html):
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                title = _clean(title)
                if not RE_LICENCIA.search(title):
                    continue
                rows.append(
                    {
                        "titulo": title,
                        "url": href,
                        "origen": "sede_tramite",
                    }
                )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _crawl_umbraco_pages(self) -> list[dict[str, Any]]:
        queue: list[str] = list(self.seed_pages)
        seen_pages: set[str] = set()
        rows: list[dict[str, Any]] = []

        while queue and len(seen_pages) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in seen_pages:
                continue
            seen_pages.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, url.rsplit("/", 1)[-1].replace("-", " "))
            blob = f"{title} {url}"
            if RE_PROYECTO.search(blob) or "urbanismo-y-vivienda" in url.lower():
                rows.append(
                    {
                        "titulo": title,
                        "url": url,
                        "fecha": _parse_fecha_dmy(html) or _parse_fecha_dmy(title),
                        "origen": "umbraco_pagina",
                    }
                )
            for href in RE_UMBRACO_LINK.findall(html):
                full = self._abs_web(href).rstrip("/")
                if full in seen_pages or full in queue:
                    continue
                queue.append(full)
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": ICV_LAYER,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{ICV_WFS}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        while start < 8000:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch(url, timeout=90)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != INE_MUN:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob,
                    "url": url,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                    "wfs_id": fid,
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue"))
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
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _umbraco_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "urbanismo-y-vivienda" not in row.get("url", "").lower():
            return None
        return self._to_proyecto(row)

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_tablon"}

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
        for item in self._crawl_umbraco_pages():
            add(self._umbraco_to_proyecto(item))
        for item in self._collect_tablon_rss():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "umbraco": sum(1 for r in rows if r.get("origen") == "umbraco_pagina"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
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
