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

WP_BASE = "https://torrelavega.es"
SEDE_BASE = "https://sede.torrelavega.es"
PGOU_BASE = "https://www.pgou-torrelavega.es"
MUNICIPIO = "Torrelavega"
ID_PREFIX = "torrelavega"
COD_INE = "39087"

URBANISMO_URL = f"{WP_BASE}/servicios-al-ciudadano/urbanismo/"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"

WFS_BASE = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
WFS_NS = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
GML_NS = "http://www.opengis.net/gml"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{PGOU_BASE}/documentos",
    f"{PGOU_BASE}/noticias",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|vado|parcelaci[oó]n|"
    r"c[eé]dula de informaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio de detalle|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"sector|alegaciones|revisi[oó]n del pgou|ordenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|oferta de empleo|subvenci[oó]n|becas|"
    r"contrato menor|licitaci[oó]n|fondos europeos sin urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"SU[-\s.]?NC\.?\s*[A-Z0-9]+|"
    r"SECTOR\s+[A-Z0-9.-]{1,12}|"
    r"S\d+[A-Z]?"
    r")\b",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?(?:pgou-torrelavega\.es|torrelavega\.es))?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_PGOU_NEWS = re.compile(
    r'href=["\'](https://www\.pgou-torrelavega\.es/noticias/[^"\']+)["\']',
    re.I,
)
RE_PGOU_DOC_PAGE = re.compile(
    r'href=["\'](https://www\.pgou-torrelavega\.es/documentos/[^"\']+)["\']',
    re.I,
)
RE_PAGE_TITLE = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_META_DATE = re.compile(
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
URB_TRAMITE_PREFIX = "URB_"


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    for parser in (_parse_fecha_iso, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = code.replace("SU NC", "SU-NC")
    return code.strip()


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "aprobación inicial" in n or "aprobacion inicial" in n:
        return "aprobación inicial"
    if "aprobación provisional" in n or "aprobacion provisional" in n:
        return "aprobación provisional"
    if "alegaciones" in n:
        return "periodo de alegaciones"
    if "revisión del pgou" in n or "revision del pgou" in n:
        return "revisión PGOU"
    if "plan parcial" in n or "plan especial" in n:
        return "planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "memoria" in n and "tomo" in n:
        return "documentación PGOU"
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
    geoms: list[dict[str, Any]] = []
    for pos in feat.findall(f".//{{{GML_NS}}}posList"):
        if pos.text:
            geom = _gml_poslist_to_polygon(pos.text.strip())
            if geom:
                geoms.append(geom)
    if not geoms:
        return None
    if len(geoms) == 1:
        return geoms[0]
    return {"type": "MultiPolygon", "coordinates": [g["coordinates"] for g in geoms]}


class TorrelavegaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress torrelavega.es + sede STA (catálogo) + pgou-torrelavega.es + SIUCAN WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgou_base = str(self.config.get("pgou_base") or PGOU_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_sector_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torrelavega/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")

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

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

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
            if ine != self.cod_ine and mun.lower() != MUNICIPIO.lower():
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
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "siucan_wfs",
                "sector_code": sector_code or None,
                "sector_name": sector_name or None,
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

    def _build_wfs_sector_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_sector_index is not None:
            return self._wfs_sector_index
        index: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wfs_proyectos():
            for token in (
                str(rec.get("sector_code") or ""),
                str(rec.get("sector_name") or ""),
                str(rec.get("titulo") or ""),
            ):
                for code in _sector_codes_from_text(token):
                    index.setdefault(code, rec)
                norm = _normalize_sector_code(token)
                if norm:
                    index.setdefault(norm, rec)
        self._wfs_sector_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "url", "pdf_url"))
        index = self._build_wfs_sector_index()
        for code in _sector_codes_from_text(blob):
            hit = index.get(code) or index.get(_normalize_sector_code(code))
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "sector_code",
                "sector_name",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            code = str(item.get("code") or "")
            name = _strip_html(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or code)
            if not name or not dboid:
                continue
            blob = f"{code} {name}"
            if not code.startswith(URB_TRAMITE_PREFIX) and not RE_LICENCIA.search(blob):
                continue
            if RE_EXCLUDE.search(blob):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "url": self._tramite_url(dboid),
                    "dboid": dboid,
                    "origen": "catalogo_sta",
                    "tramite_code": code,
                }
            )
        return rows

    def _collect_pgou_noticias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.pgou_base}/noticias")
        except urllib.error.URLError:
            return []
        urls = list(dict.fromkeys(RE_PGOU_NEWS.findall(html)))
        rows: list[dict[str, Any]] = []
        for url in urls:
            try:
                page = self._fetch(url)
            except urllib.error.URLError:
                continue
            m = RE_PAGE_TITLE.search(page)
            titulo = _strip_html(m.group(1)) if m else url.rsplit("/", 1)[-1]
            if RE_EXCLUDE.search(titulo):
                continue
            fecha = None
            md = RE_META_DATE.search(page)
            if md:
                fecha = _fecha_from_blob(md.group(1))
            if not fecha:
                fecha = _fecha_from_blob(titulo) or _fecha_from_blob(url)
            pdfs = list(dict.fromkeys(RE_PDF_HREF.findall(page)))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "origen": "pgou_noticias",
                }
            )
        return rows

    def _collect_pgou_documentos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(f"{self.pgou_base}/documentos")
        except urllib.error.URLError:
            return rows
        doc_pages = list(dict.fromkeys(RE_PGOU_DOC_PAGE.findall(html)))
        for page_url in doc_pages:
            if page_url in seen:
                continue
            seen.add(page_url)
            try:
                page = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            m = RE_PAGE_TITLE.search(page)
            titulo = _strip_html(m.group(1)) if m else page_url.rsplit("/", 1)[-1]
            pdfs = list(dict.fromkeys(RE_PDF_HREF.findall(page)))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo) or _fecha_from_blob(page_url),
                    "url": page_url,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "origen": "pgou_documentos",
                }
            )
        for pdf in dict.fromkeys(RE_PDF_HREF.findall(html)):
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "titulo": f"PGOU Torrelavega — {name}"[:500],
                    "fecha": _fecha_from_blob(pdf),
                    "url": f"{self.pgou_base}/documentos",
                    "pdf_url": pdf,
                    "origen": "pgou_documentos",
                }
            )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _row_to_licencia_tramite(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row.get("dboid") or row["titulo"]),
            "fecha_concesion": None,
            "tipo": row["titulo"][:200],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.catalogo_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "nota": "Trámite informativo sede STA (sin listado de concesiones)",
        }

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
        for item in self._collect_catalog_tramites():
            rec = self._row_to_licencia_tramite(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        info = {
            "id": _stable_id("lic", URBANISMO_URL),
            "fecha_concesion": None,
            "tipo": "urbanismo — sede y PGOU",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": "Urbanismo y planeamiento (Torrelavega)",
            "url": self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": "wp_portal",
            "nota": "Página informativa; tablón STA sin dataset embebido",
        }
        if info["id"] not in seen:
            rows.append(info)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalogo_sta": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {**stats, "added": max(0, stats["rows"] - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_pgou_noticias():
            add(self._row_to_proyecto(item))
        for item in self._collect_pgou_documentos():
            add(self._row_to_proyecto(item))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou_noticias": sum(1 for r in rows if r.get("origen") == "pgou_noticias"),
            "pgou_documentos": sum(1 for r in rows if r.get("origen") == "pgou_documentos"),
            "siucan_wfs": sum(1 for r in rows if r.get("origen") == "siucan_wfs"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": stats["rows"],
                    "added": max(0, stats["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {**stats, "added": max(0, stats["rows"] - before)}
