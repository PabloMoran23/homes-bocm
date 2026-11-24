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

SEDE_BASE = "https://sedeelectronica.valledeegues.es"
WEB_BASE = "https://www.valledeegues.com"
MUNICIPIO = "Valle de Egüés / Eguesibar"
ID_PREFIX = "valle-de-egues"

CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
CATALOGO_URBANISMO = f"{SEDE_BASE}/catalogoservicios.aspx?area=146&ambito=16"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"

PGM_WEB = (
    f"{WEB_BASE}/plan-general-municipal-del-valle-de-egues-estrategia-y-modelo-de-ocupacion-territorial/"
)
VISOR_IDENA = "https://geoportal.navarra.es/es/visores"

WFS_URL = "https://idena.navarra.es/ogc/wfs"
WFS_LAYER = "IDENA:INFOTU_Pol_PlanUrbMun"
WFS_MUNI_FILTER = "MUNICIPIO ILIKE '%Eg%es%'"

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=3199",
        "titulo": "LICENCIA de obras",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=5943",
        "titulo": "DECLARACIÓN responsable obras",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=5960",
        "titulo": "LICENCIA obra – Autoliquidación",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=5964",
        "titulo": "LICENCIA de Primera utilización – Solicitud",
    },
    {
        "url": f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=5955",
        "titulo": "LICENCIA de actividad",
    },
]

DEFAULT_WEB_SEEDS: list[dict[str, str]] = [
    {
        "titulo": "Plan General Municipal — Estrategia y Modelo de Ocupación Territorial",
        "url": PGM_WEB,
    },
    {
        "titulo": "Visor cartográfico IDENA (Geoportal Navarra)",
        "url": VISOR_IDENA,
    },
]

RE_TRAMITE = re.compile(
    r'href="(https://sedeelectronica\.valledeegues\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"\s*([^<]+)",
    re.I,
)
RE_TABLON_ROW = re.compile(
    r'anuncio\.aspx\?id=(\d+)"[^>]*>.*?lblFecha">([^<]+)</span>.*?<td>\s*([^<]+?)\s*</td>',
    re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"primera utilizaci[oó]n|obra[s]?|autoliquidaci[oó]n|instalaci[oó]n.*impresi[oó]n 3d)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan general|pgm|modificaci[oó]n pormenoriz|bando.*aprobaci|"
    r"informaci[oó]n p[uú]blica|parcel|pol[\s\.]?\d|expedient|edicto.*isivtnu|"
    r"plusval[ií]a|modelo de ocupaci|estrategia territorial|visor|idena|siun)",
)
RE_NOISE = re.compile(
    r"(?i)(servicios m[ií]nimos|huelga|empleo p[uú]blico|oficial admvo|prueba te[oó]rica|"
    r"escuela de m[uú]sica|calendario escolar|convocatoria.*plaza|subvenci[oó]n deport|"
    r"barra bar fiestas|pruebas f[ií]sicas|saldos y cuentas)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    if "modificaci" in n and "pormenoriz" in n:
        return "modificación pormenorizada"
    if "bando" in n and "aprobaci" in n:
        return "bando / aprobación inicial"
    if "plan general" in n or "pgm" in n or "modelo de ocupaci" in n:
        return "plan general municipal"
    if "edicto" in n and "isivtnu" in n:
        return "edicto fiscal / plusvalía"
    if "licencia" in n or "obra" in n:
        return "trámite de obra"
    if "visor" in n or "idena" in n:
        return "cartografía / visor"
    return "urbanismo"


class ValleDeEguesAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Sedipualba (tablón RSS/HTML + catálogo trámites) + web PGM + IDENA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_seeds = list(self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)
        self.licencia_tramites = list(self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES)
        geom = self.config.get("geometry") or {}
        self.wfs_url = str(geom.get("wfs_url") or WFS_URL).rstrip("/")
        self.wfs_layer = str(geom.get("type_name") or WFS_LAYER)
        self.wfs_filter = str(geom.get("cql_filter") or WFS_MUNI_FILTER)
        self._plan_muni: dict[str, Any] | None = None

    def _fetch(self, url: str, *, timeout: int = 45, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valle-de-egues/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if encoding == "latin-1":
                return raw.decode("latin-1", errors="replace")
            return raw.decode(encoding, errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 45) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valle-de-egues/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _wfs_query_url(self) -> str:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": self.wfs_layer,
            "count": "5",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": self.wfs_filter,
        }
        return f"{self.wfs_url}?{urllib.parse.urlencode(params)}"

    def _fetch_plan_municipal_wfs(self) -> dict[str, Any] | None:
        if self._plan_muni is not None:
            return self._plan_muni
        url = self._wfs_query_url()
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
            self._plan_muni = None
            return None
        features = data.get("features") or []
        if not features:
            self._plan_muni = None
            return None
        feat = features[0]
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        rec: dict[str, Any] = {
            "titulo": f"Planeamiento urbanístico municipal vigente — {props.get('MUNICIPIO') or MUNICIPIO}",
            "url": props.get("URLSIUN") or PGM_WEB,
            "fecha": None,
            "tipo": "plan general municipal",
            "origen": "idena_wfs",
            "instrumento": props.get("INSTRUMENT"),
            "wfs_id": feat.get("id"),
        }
        if isinstance(geom, dict) and geom.get("coordinates"):
            rec["geom_geojson"] = geom
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = url
            rec["coord_source"] = "portal_geometry_centroid"
            rec["coordinates_crs"] = "EPSG:4326"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        self._plan_muni = rec
        return rec

    def _collect_tramites_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for catalog_url in (CATALOGO_URBANISMO, CATALOGO_URL):
            try:
                html = self._fetch(catalog_url, timeout=30)
            except urllib.error.URLError:
                continue
            for href, title in RE_TRAMITE.findall(html):
                if href in seen:
                    continue
                seen.add(href)
                rows.append({"titulo": _clean(title), "url": href, "origen": "catalogo_tramites"})
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS, timeout=30, encoding="latin-1")
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
            if title and link:
                rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _collect_tablon_html(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, timeout=30)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            anuncio_id, fechas, title = m.group(1), _clean(m.group(2)), _clean(m.group(3))
            fecha = _parse_fecha_dmy(fechas.split("-")[0].strip())
            url = f"{self.sede_base}/tablondeanuncios/anuncio.aspx?id={anuncio_id}"
            rows.append({"titulo": title, "url": url, "fecha": fecha, "origen": "tablon_html"})
        return rows

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        return [
            {"titulo": s["titulo"], "url": s["url"], "fecha": None, "origen": "web_semilla"}
            for s in self.web_seeds
        ]

    def _attach_muni_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        if rec.get("origen") != "idena_wfs":
            return
        plan = self._fetch_plan_municipal_wfs()
        if not plan or not plan.get("geom_geojson"):
            return
        rec["geom_geojson"] = plan["geom_geojson"]
        rec["geometry_crs"] = plan.get("geometry_crs") or "EPSG:4326"
        rec["geometry_source"] = plan.get("geometry_source")
        rec["geometry_source_url"] = plan.get("geometry_source_url")
        rec["coord_source"] = plan.get("coord_source")
        rec["coordinates_crs"] = plan.get("coordinates_crs") or "EPSG:4326"
        if plan.get("lat") is not None:
            rec["lat"], rec["lon"] = plan["lat"], plan["lon"]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        tit = row["titulo"]
        if not RE_LICENCIA.search(tit):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia (informativo)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": tit,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Catálogo sede Sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(r"(?i)licencia", blob):
            return None
        return {
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
            "instrumento",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "geometry_crs",
            "coord_source",
            "coordinates_crs",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_muni_geometry(rec)
        return rec

    def _filter_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if row.get("origen") in {"idena_wfs", "web_semilla"}:
            return self._to_proyecto(row)
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self.licencia_tramites:
            add(self._tramite_to_licencia({**item, "origen": "tramite_seed"}))
        for item in self._collect_tramites_catalog():
            add(self._tramite_to_licencia(item))
        for item in self._collect_tablon_rss():
            add(self._tablon_to_licencia(item))
        for item in self._collect_tablon_html():
            add(self._tablon_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon_tramites"}

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

        plan = self._fetch_plan_municipal_wfs()
        if plan:
            add(self._to_proyecto(plan))
        for item in self._collect_web_seeds():
            add(self._filter_proyecto(item))
        for item in self._collect_tramites_catalog():
            if RE_PROYECTO.search(item["titulo"]) or RE_LICENCIA.search(item["titulo"]):
                add(self._filter_proyecto(item))
        for item in self._collect_tablon_rss():
            add(self._filter_proyecto(item))
        for item in self._collect_tablon_html():
            add(self._filter_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "idena_wfs": sum(1 for r in rows if r.get("origen") == "idena_wfs"),
            "web_semilla": sum(1 for r in rows if r.get("origen") == "web_semilla"),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
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
