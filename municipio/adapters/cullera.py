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

BASE = "https://www.cullera.es"
SEDE = "https://cullera.sedipualba.es"
URBANISMO_URL = f"{BASE}/es/pagina/urbanismo"
TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx"
VISOR_GVSIG = (
    "https://cullera.gvsigonline.com/gvsigonline/core/load_public_project/UrbanismeConsultes/"
)
MUNICIPIO = "Cullera"
ID_PREFIX = "cullera"
COD_INE_MUN = "46105"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(0, 14000, 500))

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|obra[s]? (?:mayor|menor)|ocupaci[oó]n|parcelaci[oó]n|"
    r"segregaci[oó]n|derribo|desmonte|explanaci[oó]n|compatibilidad urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|ue-|prr-|prm-|npr-|npi-|suz|homologaci[oó]n|"
    r"normas urban|ordenanza|dogv|bop|aprobaci[oó]n|alineaci[oó]n|vega port|mareny)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|empleo p[uú]blico|matrimonio|becas|subvenci[oó]n|"
    r"modificaci[oó]n de cr[eé]ditos|presupuest|fallas|teatre|platges|gatos ferales|"
    r"plusval[ií]a|multas de tr[aá]fico|comisi[oó]n de servicios)",
)
RE_TRAMITE = re.compile(
    r'href="(https://cullera\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_URBANISMO_LINK = re.compile(
    r'href="([^"]+)"[^>]*>([^<]{8,300})',
    re.I,
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|PRR|PRM|NPR|NPI|SECTOR|MARENY|VEGA|JULUNA|BROSQUIL|AQUASOL)[\s\-]?[\dA-ZÁÉÍÓÚ'._/\-]+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


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
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n or "prr-" in n or "prm-" in n:
        return "plan parcial"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "convenio" in n:
        return "convenio urbanístico"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "reparcel" in n:
        return "reparcelación"
    if "homologaci" in n:
        return "homologación planeamiento"
    if "normas urban" in n or "normes urban" in n:
        return "normas urbanísticas"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        g = feat.get("geometry")
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


class CulleraAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede sedipualba + ICV WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.catalogo_tramites = str(self.config.get("catalogo_tramites") or CATALOGO_TRAMITES)
        self.visor_url = str(self.config.get("visor_url") or VISOR_GVSIG)
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_cache: list[dict[str, Any]] | None = None
        self._icv_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cullera/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        return json.loads(self._fetch(url, timeout=timeout))

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
        try:
            html = self._fetch(self.catalogo_tramites)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title in RE_TRAMITE.findall(html):
            titulo = _clean(unescape(title))
            rows.append({"titulo": titulo, "url": href, "origen": "sede_tramite"})
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss)
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

    def _collect_urbanismo_web(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_URBANISMO_LINK.findall(html):
            titulo = _clean(title)
            if len(titulo) < 8:
                continue
            blob = f"{titulo} {href}"
            if not RE_PROYECTO.search(blob) and "urbanisme" not in href.lower():
                continue
            if href.startswith("/"):
                url = f"{self.web_base}{href}"
            elif href.startswith("http"):
                url = href
            else:
                url = f"{self.web_base}/{href.lstrip('/')}"
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": _parse_fecha_dmy(titulo),
                    "origen": "web_urbanismo",
                }
            )
        return rows

    def _icv_wfs_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": type_name,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": "500",
                "startIndex": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _feature_to_icv_row(self, feat: dict[str, Any], *, layer: str) -> dict[str, Any] | None:
        props = feat.get("properties") or {}
        if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
            return None
        fid = str(props.get("id") or props.get("fid") or "")
        pp = _clean(str(props.get("pp") or ""))
        ue = _clean(str(props.get("ue") or ""))
        denom = _clean(str(props.get("denominaci") or props.get("denominaci_val") or ""))
        clas = _clean(str(props.get("clasificacion") or ""))
        f_aprob = props.get("f_aprob") or props.get("f_public")
        titulo = denom or pp or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"
        geom = feat.get("geometry")
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": str(f_aprob)[:10] if f_aprob else None,
            "url": self.visor_url,
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "clasificacion": clas or None,
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if isinstance(geom, dict) and geom.get("coordinates"):
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._icv_wfs_url(
                self.icv_layer_su if layer == "su" else self.icv_layer_zon,
                0,
            )
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._icv_cache is not None:
            return self._icv_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "su"), (self.icv_layer_zon, "zon")):
            empty_pages = 0
            for start in self.icv_offsets:
                url = self._icv_wfs_url(type_name, start)
                try:
                    data = self._fetch_json(url, timeout=120)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                batch = data.get("features") or []
                if not batch:
                    break
                page_hits = 0
                for feat in batch:
                    rec = self._feature_to_icv_row(feat, layer=layer)
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                        page_hits += 1
                if page_hits == 0:
                    empty_pages += 1
                    if empty_pages >= 6:
                        break
                else:
                    empty_pages = 0
        self._icv_cache = rows
        self._icv_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._icv_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._icv_by_key[tok.lower()] = rec
        return rows

    def _match_icv(self, text: str) -> dict[str, Any] | None:
        if self._icv_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._icv_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._icv_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "pp", "ue"))
        hit = self._match_icv(blob)
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
        for item in self._collect_urbanismo_web():
            add(self._to_proyecto(item))
        for item in self._collect_tablon_rss():
            add(self._tablon_to_proyecto(item))
        add(
            {
                "id": _stable_id("proy", self.visor_url),
                "municipio": MUNICIPIO,
                "titulo": "Visor cartográfico urbanístico — gvsigonline Cullera",
                "fecha": None,
                "tipo": "visor GIS",
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "visor",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "web_urbanismo": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
