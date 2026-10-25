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

BASE = "https://www.portugalete.org"
MUNICIPIO = "Portugalete"
ID_PREFIX = "portugalete"

TABLON_URL = f"{BASE}/es-ES/Tramites/tablonanuncios/ayuntamiento/Paginas/default.aspx"
OPENDATA_CATALOG = "https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-portugalete"
OPENDATA_GLOBAL_JSON = (
    "https://www.opendatabizkaia.eus/es/datastore/dump/"
    "1bf67aeb-8a08-4df4-9f8c-3392c88dbcda/"
    "datos-globales-planeamiento-portugalete-2023-2026?format=json"
)
ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/Plangintza_Planeamiento/MapServer"
)

DEFAULT_SEED_PAGES: list[tuple[str, str]] = [
    (f"{BASE}/es-ES/Servicios/Urbanismo/Paginas/default.aspx", "Urbanismo — servicio municipal"),
    (f"{BASE}/es-ES/VivirenPortugalete/UrbanismoyObras/Paginas/default.aspx", "Urbanismo y Obras"),
    (
        f"{BASE}/es-ES/Ayuntamiento/TramitesCiudadanos/Paginas/Urbanismo.aspx",
        "Trámites ciudadanos — Urbanismo",
    ),
    (
        f"{BASE}/es-ES/Ayuntamiento/Corporacionmunicipal/Paginas/ConsejoAsesordePlaneamientoMunicipal.aspx",
        "Consejo Asesor de Planeamiento Municipal",
    ),
]

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    (
        f"{BASE}/es-ES/Ayuntamiento/TramitesCiudadanos/Paginas/Urbanismo_Licenciaactividadclasificada.aspx",
        "Licencia de actividad clasificada",
    ),
    (
        f"{BASE}/es-ES/Ayuntamiento/TramitesCiudadanos/Paginas/"
        "Urbanismo_Licenciaobrasmenoresendominiopublico.aspx",
        "Licencia de obras menores en dominio público",
    ),
]

# Capas 1.1–1.3 clasificación del suelo (Plangintza_Planeamiento)
CLASIFICACION_LAYERS: tuple[tuple[int, str], ...] = (
    (1, "Urbano"),
    (2, "Urbanizable"),
    (3, "No urbanizable"),
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra(s)?\s+(?:menor|mayor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"ordenanza.*(?:tr[aá]fico|movilidad)|consulta p[uú]blica|calificaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TABLON_BLOCK = re.compile(
    r"-\s*(?P<titulo>[^\n<]+?)\s*"
    r"Remitente:\s*(?P<remitente>[^\n<]+?)\s*"
    r"Categor[ií]a:\s*(?P<categoria>[^\n<]+?)\s*"
    r"Tiempo de vigencia:\s*(?P<vigencia>\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})",
    re.S,
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str | None) -> str | None:
    if not text:
        return None
    m = RE_FECHA_DMY.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _vigencia_start(vigencia: str) -> str | None:
    part = (vigencia or "").split("-", 1)[0].strip()
    return _parse_fecha_dmy(part)


def _tipo_proyecto(titulo: str) -> str:
    blob = (titulo or "").lower()
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "plan especial" in blob:
        return "plan especial"
    if "plan parcial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "consulta pública" in blob or "informaci" in blob:
        return "información pública"
    if "ordenanza" in blob and ("tráfico" in blob or "movilidad" in blob):
        return "ordenanza urbanística"
    if "calificaci" in blob:
        return "calificación urbanística"
    return "planeamiento / urbanismo"


class PortugaleteAyuntamientoAdapter(AyuntamientoAdapter):
    """
    SharePoint portugalete.org (tablón + trámites) + Open Data Bizkaia + ArcGIS Diputación.
    """

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.portal_timeout_s = int(self.config.get("portal_timeout_s", 12))
        self.opendata_timeout_s = int(self.config.get("opendata_timeout_s", 15))
        raw_tram = self.config.get("licencia_tramites")
        if raw_tram:
            self.licencia_tramites = [(str(t[0]), str(t[1])) for t in raw_tram if len(t) >= 2]
        else:
            self.licencia_tramites = list(DEFAULT_LICENCIA_TRAMITES)
        raw_seeds = self.config.get("seed_pages")
        if raw_seeds:
            self.seed_pages = [(str(s[0]), str(s[1])) for s in raw_seeds if len(s) >= 2]
        else:
            self.seed_pages = list(DEFAULT_SEED_PAGES)
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.clasificacion_layers = tuple(
            (int(a), str(b))
            for a, b in (self.config.get("clasificacion_layers") or CLASIFICACION_LAYERS)
        )

    def _fetch(
        self,
        url: str,
        *,
        timeout_s: int | None = None,
        data: bytes | None = None,
    ) -> bytes:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-portugalete/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s or self.portal_timeout_s) as resp:
            return resp.read()

    def _fetch_text(self, url: str, *, timeout_s: int | None = None) -> str:
        return self._fetch(url, timeout_s=timeout_s).decode("utf-8", errors="replace")

    def _safe_fetch_text(self, url: str, *, timeout_s: int | None = None) -> str | None:
        try:
            return self._fetch_text(url, timeout_s=timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

    def _fetch_json(self, url: str, *, timeout_s: int | None = None) -> Any:
        return json.loads(self._fetch(url, timeout_s=timeout_s))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<title>([^<]+)", r"<h1[^>]*>([^<]+)", r"<h2[^>]*>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if len(t) > 3:
                    return t[:500]
        return fallback

    def _parse_tablon(self, html: str) -> list[dict[str, Any]]:
        text = _strip_html(html)
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_BLOCK.finditer(text):
            titulo = m.group("titulo").strip()
            if len(titulo) < 8:
                continue
            fecha = _vigencia_start(m.group("vigencia"))
            pdf_url = None
            chunk_start = max(0, m.start() - 200)
            chunk_end = min(len(html), m.end() + 800)
            chunk = html[chunk_start:chunk_end]
            pdf_m = RE_PDF_HREF.search(chunk)
            if pdf_m:
                pdf_url = pdf_m.group(1)
                if pdf_url.startswith("/"):
                    pdf_url = urllib.parse.urljoin(BASE, pdf_url)
            key = f"{titulo}-{fecha or ''}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": pdf_url or TABLON_URL,
                    "categoria": m.group("categoria").strip(),
                    "remitente": m.group("remitente").strip(),
                    "origen": "tablon_sharepoint",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        html = self._safe_fetch_text(TABLON_URL, timeout_s=self.portal_timeout_s)
        if not html:
            return []
        return self._parse_tablon(html)

    def _arcgis_clasificacion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for layer_id, label in self.clasificacion_layers:
            params = {
                "where": "Municipio='PORTUGALETE'",
                "outFields": "Municipio,ClasificacionCA,OBJECTID",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "1",
            }
            url = f"{self.arcgis_map}/{layer_id}/query?{urllib.parse.urlencode(params)}"
            try:
                data = self._fetch_json(url, timeout_s=45)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                continue
            feats = data.get("features") if isinstance(data, dict) else None
            if not feats:
                continue
            geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
            if not isinstance(geom, dict):
                continue
            titulo = f"PGOU Portugalete — suelo {label} (Diputación Foral de Bizkaia)"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"arcgis-clas-{layer_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": "2023-01-01",
                "tipo": "PGOU",
                "url": OPENDATA_CATALOG,
                "source": "ayuntamiento",
                "origen": "diputacion_arcgis_clasificacion",
                "geom_geojson": geom,
                "geometry_source": "portal_visor_arcgis",
                "geometry_source_url": url,
                "coord_source": "portal_geometry_centroid",
                "geometry_crs": "EPSG:4326",
            }
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_opendata_global(self) -> list[dict[str, Any]]:
        try:
            data = self._fetch_json(OPENDATA_GLOBAL_JSON, timeout_s=self.opendata_timeout_s)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            return []
        if not isinstance(data, list) or not data:
            return []
        rows: list[dict[str, Any]] = []
        for i, item in enumerate(data[:40]):
            if not isinstance(item, dict):
                continue
            parts = [str(v) for v in item.values() if v not in (None, "", " ")]
            titulo = " — ".join(parts[:4])[:500] if parts else f"Planeamiento Portugalete fila {i + 1}"
            if not RE_PROYECTO.search(titulo) and "planeamiento" not in titulo.lower():
                titulo = f"Datos globales planeamiento Portugalete: {titulo}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"opendata-global-{i}-{titulo[:80]}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": "2023-01-01",
                "tipo": _tipo_proyecto(titulo),
                "url": OPENDATA_GLOBAL_JSON,
                "source": "ayuntamiento",
                "origen": "opendatabizkaia_global",
            }
            rows.append(rec)
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, label in self.seed_pages:
            html = self._safe_fetch_text(url, timeout_s=self.portal_timeout_s)
            title = self._page_title(html or "", label) if html else label
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": None,
                "tipo": _tipo_proyecto(title),
                "url": url,
                "source": "ayuntamiento",
                "origen": "portal_semilla",
            }
            if html:
                for pdf_m in RE_PDF_HREF.finditer(html):
                    pdf = pdf_m.group(1)
                    if pdf.startswith("/"):
                        pdf = urllib.parse.urljoin(BASE, pdf)
                    if RE_PROYECTO.search(pdf) or "pgou" in pdf.lower() or "urban" in pdf.lower():
                        rec["url"] = pdf
                        break
            rows.append(rec)
        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        cat = row.get("categoria") or ""
        blob = f"{titulo} {cat}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", f"tablon-{titulo}-{row.get('fecha') or ''}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _tipo_proyecto(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "categoria_tablon": cat or None,
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", f"tablon-{titulo}-{row.get('fecha') or ''}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": "anuncio tablón (licencia/obra)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, label in self.licencia_tramites:
            html = self._safe_fetch_text(url, timeout_s=self.portal_timeout_s)
            title = self._page_title(html or "", label) if html else label
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; sin listado público de concesiones",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._arcgis_clasificacion_rows():
            by_id[rec["id"]] = rec
        for rec in self._collect_opendata_global():
            by_id[rec["id"]] = rec
        for rec in self._collect_seed_pages():
            by_id[rec["id"]] = rec
        for row in self._collect_tablon():
            rec = self._tablon_to_proyecto(row)
            if rec:
                by_id[rec["id"]] = rec
        if not by_id:
            by_id[_stable_id("proy", OPENDATA_CATALOG)] = {
                "id": _stable_id("proy", OPENDATA_CATALOG),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico Portugalete (catálogo Open Data Bizkaia)",
                "fecha": "2023-01-01",
                "tipo": "PGOU",
                "url": OPENDATA_CATALOG,
                "source": "ayuntamiento",
                "origen": "opendata_catalog_fallback",
            }
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._collect_licencia_tramites():
            by_id[rec["id"]] = rec
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if rec:
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "source": "arcgis_opendata_tablon",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
