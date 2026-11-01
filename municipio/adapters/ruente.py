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
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WP_BASE = "https://ruente.es"
MUNICIPIO = "Ruente"
ID_PREFIX = "ruente"
COD_INE = "39066"

BANDOS_URL = f"{WP_BASE}/bandos-y-anuncios/"
ORDENANZAS_URL = f"{WP_BASE}/ordenanzas/"
SEDE_URL = "https://ruente.sedelectronica.es/"
TRANSPARENCIA_ORDENACION = (
    "https://ruente.cumpletransparencia.es/Ruente/Ordenacion"
)
AUCAN_URL = "https://aplicacionesweb.cantabria.es/aucan/public/zona/saja/ruente"

WFS_BASE = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
WFS_NS = WFS_BASE

AUCAN_PLANEAMIENTO: list[dict[str, Any]] = [
    {
        "titulo": "Normas Subsidiarias Municipales de Ruente (CRU 05/07/1983; BOC 06/08/1983)",
        "fecha": "1983-08-06",
        "tipo": "normas subsidiarias",
        "url": AUCAN_URL,
        "nota": "Planeamiento general vigente; modificaciones puntuales en AUCAN.",
    },
    {
        "titulo": "Modificaciones puntuales de las Normas Subsidiarias — archivo AUCAN",
        "fecha": None,
        "tipo": "modificación planeamiento",
        "url": AUCAN_URL,
        "nota": "Listado documental en Archivo Urbanístico de Cantabria (AUCAN).",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|informaci[oó]n p[uú]blica de solicitud|"
    r"concesi[oó]n de licencia|obra (?:mayor|menor)|construcciones, instalaciones y obras)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"urbanizaci[oó]n|sector|suelo|ordenanza (?:fiscal|reguladora)|"
    r"exposici[oó]n p[uú]blica|plan parcial|dus\s*5000|alumbrado|áreas degradadas|"
    r"infraestructuras agrarias)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|funcionario|promoci[oó]n interna|becas|"
    r"registro de pe[nñ]as|convocatoria.*plaza|empleo p[uú]blico|"
    r"gymkana|fiestas|sendero adaptado|btt\b|pastos del ayuntamiento|"
    r"teleasistencia|atenci[oó]n a domicilio|ivtm|iae\b|ibi\b|basuras|alcantarillado|"
    r"agua\b|veh[ií]culos|mercadillo|puestos, barracas)",
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, wp_date: str | None = None) -> str | None:
    if wp_date:
        d = _iso_date_wp(wp_date)
        if d:
            return d
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "normas subsidiarias" in n or "pgou" in n:
        return "normas subsidiarias / PGOU"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "dus" in n or "alumbrado" in n:
        return "proyecto de infraestructura"
    if "áreas degradadas" in n or "areas degradadas" in n:
        return "ordenación territorial"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lng, lat = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    gml_ns = "http://www.opengis.net/gml"
    geoms: list[dict[str, Any]] = []
    for pos in feat.findall(f".//{{{gml_ns}}}posList"):
        if pos.text:
            geom = _gml_poslist_to_polygon(pos.text.strip())
            if geom:
                geoms.append(geom)
    if not geoms:
        return None
    if len(geoms) == 1:
        return geoms[0]
    return {"type": "MultiPolygon", "coordinates": [g["coordinates"] for g in geoms]}


class RuenteAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ruente.es (bandos/ordenanzas REST) + AUCAN Cantabria (planeamiento documental)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = f"{self.wp_base}/wp-json/wp/v2"
        self.bandos_url = str(self.config.get("bandos_url") or BANDOS_URL)
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.sede_url = str(self.config.get("sede_url") or SEDE_URL)
        self.aucan_url = str(self.config.get("aucan_url") or AUCAN_URL)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ruente/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _iter_wp_posts(self, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 20:
            q = {"per_page": "100", "page": str(page), **{k: str(v) for k, v in params.items()}}
            url = f"{self.wp_api}/posts?{urllib.parse.urlencode(q)}"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            for post in batch:
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content_html = post.get("content", {}).get("rendered", "") or ""
                blob = f"{title} {_strip_html(content_html)}"
                pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content_html)]
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(blob, post.get("date")),
                        "url": post.get("link") or self.bandos_url,
                        "pdf_url": pdfs[0] if pdfs else None,
                        "pdf_urls": pdfs,
                        "blob": blob,
                        "origen": "wp_rest",
                    }
                )
            if len(batch) < 100:
                break
            page += 1
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        sources: list[tuple[str, dict[str, Any]]] = [
            ("bandos", {"categories": 11}),
            ("ordenanzas", {"categories": 10}),
        ]
        for term in ("urbanismo", "licencia", "ordenanza", "planeamiento", "pgou"):
            sources.append((f"search:{term}", {"search": term}))
        for _label, params in sources:
            for row in self._iter_wp_posts(**params):
                key = row.get("url") or row.get("titulo")
                if key in seen:
                    continue
                seen.add(key)
                out.append(row)
        return out

    def _wfs_query_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "1.1.0",
                "request": "GetFeature",
                "typeName": "Urbanismo:Sectores",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "maxFeatures": "5000",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        url = self._wfs_query_url()
        try:
            raw = self._fetch(url)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            self._wfs_cache = rows
            return rows

        for feat in root.findall(f".//{{{WFS_NS}}}Sectores"):
            ine = feat.findtext(f"{{{WFS_NS}}}Código_INE") or ""
            mun = feat.findtext(f"{{{WFS_NS}}}Denominación_Municipio") or ""
            if ine != self.cod_ine and mun.upper() != MUNICIPIO.upper():
                continue
            sector_code = _strip_html(feat.findtext(f"{{{WFS_NS}}}Código_Sector") or "")
            sector_name = _strip_html(feat.findtext(f"{{{WFS_NS}}}Denominación_Sector") or "")
            titulo = sector_name or sector_code or "Sector urbanístico"
            if sector_code and sector_code not in titulo:
                titulo = f"{sector_code} — {titulo}"
            geom = _gml_feature_to_geojson(feat)
            key = f"{sector_code}:{sector_name}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{key}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": "sector urbanístico",
                "url": self.aucan_url,
                "source": "ayuntamiento",
                "origen": "siucan_wfs",
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _collect_aucan_planeamiento(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in AUCAN_PLANEAMIENTO:
            key = item["titulo"]
            rows.append(
                {
                    "titulo": item["titulo"],
                    "fecha": item.get("fecha"),
                    "url": item.get("url") or self.aucan_url,
                    "tipo_hint": item.get("tipo"),
                    "nota": item.get("nota"),
                    "origen": "aucan_planeamiento",
                    "blob": item["titulo"],
                }
            )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('blob', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and "ordenanza" not in blob.lower() and "plan" not in blob.lower():
            if "proyecto" not in blob.lower() and "dus" not in blob.lower():
                return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo_hint") or _proyecto_tipo(blob),
            "url": row.get("url") or self.bandos_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("nota"):
            rec["nota"] = row["nota"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.bandos_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "pdf_url": row.get("pdf_url"),
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (self.sede_url, "sede electrónica — trámites urbanísticos"),
            (
                f"{self.wp_base}/ordenanza-fiscal-reguladora-de-la-tasa-por-licencias-urbanisticas/",
                "ordenanza fiscal — tasa por licencias urbanísticas",
            ),
            (
                f"{self.wp_base}/ordenanza-fiscal-sobre-construcciones-instalaciones-y-obras/",
                "ordenanza fiscal — construcciones, instalaciones y obras",
            ),
            (self.bandos_url, "bandos y anuncios municipales"),
            (self.aucan_url, "AUCAN — planeamiento urbanístico municipal"),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "wp_tramite",
                }
            )
        return rows

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
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_posts():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_wp_posts():
            rec = self._row_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_wp_posts():
            add(self._row_to_proyecto(item))
        for item in self._collect_aucan_planeamiento():
            add(self._row_to_proyecto(item))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "aucan_planeamiento": sum(1 for r in rows if r.get("origen") == "aucan_planeamiento"),
            "siucan_wfs": sum(1 for r in rows if r.get("origen") == "siucan_wfs"),
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
