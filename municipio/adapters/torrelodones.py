from __future__ import annotations

import hashlib
import json
import math
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_bbox, geometry_centroid, record_geometry

WP_BASE = "https://torrelodones.es"
SEDE_BASE = "https://sede.torrelodones.es"
MUNICIPIO = "Torrelodones"
ID_PREFIX = "torrelodones"

BOARD_DEFAULT = f"{SEDE_BASE}/board"
NORMAS_URL = f"{WP_BASE}/normas-subsidiarias/"
URBANISMO_URL = f"{WP_BASE}/urbanismo/"

ARC_GIS_SECTORS = (
    "https://services1.arcgis.com/SwZwNQ29xwi3dduD/arcgis/rest/services/"
    "Normas_Subsidarias_Sectores_Urbanisticos_SYKGIS/FeatureServer/0"
)

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{URBANISMO_URL}obras-sujetas-a-licencia/",
    (
        f"{URBANISMO_URL}"
        "obras-o-actuaciones-urbanisticas-que-no-precisan-licencia-pero-si-declaracion-responsable/"
    ),
    f"{URBANISMO_URL}ocupaciones-via-publica/",
    f"{URBANISMO_URL}licencia-actividad/",
    (
        f"{URBANISMO_URL}"
        "obras-o-actuaciones-menor-entidad-que-no-precisan-titulo-habilitante-ni-licencia-ni-declaracion-responsable/"
    ),
]

DEFAULT_AVISO_SEARCHES: list[str] = [
    "proyecto mejora urbanizacion",
    "proyecto urbanizacion",
    "urbanizacion arroyo",
    "urbanizacion montealegre",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"convenio|informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|urbanizaci[oó]n|obra p[uú]blica|"
    r"accesibilidad|alumbrado)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./_-](\d{2})[./_-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'class="([^"]+)"[^>]*data-label="([^"]+)"[^>]*>(.*?)</td>',
    re.I | re.S,
)
RE_SECTOR_CODE = re.compile(
    r"\b(S-\d{1,3}|APD-\d{1,3}|AHS|AP[A-Z]?-\d{1,3}|P_COD[_\s:]?[A-Z0-9-]+)\b",
    re.I,
)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<h1[^>]*class=\"[^\"]*elementor-heading-title[^\"]*\"[^>]*>([^<]+)",
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Torrelodones.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    t = title.lower()
    if "normas subsidiarias" in t or "nnss" in t or "pgou" in t:
        return "planeamiento"
    if "informaci" in t and "públic" in t:
        return "información pública"
    if "convenio" in t:
        return "convenio"
    if "urbaniz" in t or "accesibilidad" in t or "alumbrado" in t:
        return "obra pública"
    if "licencia" in t:
        return "licencia publicada"
    return "urbanismo"


class TorrelodonesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (normas/avisos) + tablón eHome sede + ArcGIS sectores NNSS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_DEFAULT)
        self.normas_url = str(self.config.get("normas_url") or NORMAS_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.aviso_searches = [str(s) for s in (self.config.get("aviso_searches") or DEFAULT_AVISO_SEARCHES)]
        geom_cfg = self.config.get("geometry") or {}
        self.arcgis_layer = str(geom_cfg.get("base_url") or ARC_GIS_SECTORS).rstrip("/")
        if not self.arcgis_layer.endswith("/0"):
            layer_id = int(geom_cfg.get("layer_id", 0))
            self.arcgis_layer = f"{self.arcgis_layer.rstrip('/')}/{layer_id}"
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sector_cache: dict[str, dict[str, Any]] | None = None
        self._municipio_centroid: tuple[float, float] | None = None

    def _fetch(self, url: str, *, use_ssl_ctx: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torrelodones/1.0")},
        )
        needs_insecure = use_ssl_ctx or any(
            host in url for host in ("sede.torrelodones.es", "torrelodones.es")
        )
        ctx = self._ssl_ctx if needs_insecure and self.config.get("insecure_ssl", True) else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, use_ssl_ctx: bool = False) -> Any:
        return json.loads(self._fetch(url, use_ssl_ctx=use_ssl_ctx))

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(base, href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            out.append(self._abs_url(m.group(1)))
        return list(dict.fromkeys(out))

    def _load_sector_index(self) -> dict[str, dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        index: dict[str, dict[str, Any]] = {}
        query = (
            f"{self.arcgis_layer}/query?"
            "where=1%3D1&outFields=TXT_LABEL,P_COD,P_CL,LINK,LINK_NORMA"
            "&returnGeometry=true&outSR=4326&f=geojson&resultRecordCount=200"
        )
        try:
            data = self._fetch_json(query)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sector_cache = index
            return index
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
                continue
            for key in ("TXT_LABEL", "P_COD", "P_CL"):
                code = str(props.get(key) or "").strip()
                if not code:
                    continue
                index[code.upper()] = {
                    "geom_geojson": geom,
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": query,
                    "sector_code": code,
                }
        self._sector_cache = index
        return index

    def _centroid_from_sectors(self) -> tuple[float, float] | None:
        if self._municipio_centroid is not None:
            return self._municipio_centroid
        index = self._load_sector_index()
        lngs: list[float] = []
        lats: list[float] = []
        for hit in index.values():
            geom = hit.get("geom_geojson")
            if not isinstance(geom, dict):
                continue
            bbox = geometry_bbox(geom)
            if not bbox:
                continue
            min_lng, min_lat, max_lng, max_lat = bbox
            lngs.extend([min_lng, max_lng])
            lats.extend([min_lat, max_lat])
        if not lngs:
            return None
        self._municipio_centroid = ((min(lats) + max(lats)) / 2.0, (min(lngs) + max(lngs)) / 2.0)
        return self._municipio_centroid

    def _jitter_coords(self, base_lat: float, base_lng: float, key: str) -> tuple[float, float]:
        h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
        angle = (h % 360) * math.pi / 180.0
        dist = ((h >> 8) % 1000) / 1000.0 * 180.0
        dlat = (dist * math.cos(angle)) / 111_320.0
        dlng = (dist * math.sin(angle)) / (111_320.0 * max(0.2, math.cos(math.radians(base_lat))))
        return base_lat + dlat, base_lng + dlng

    def _apply_coords_fallback(self, rows: list[dict[str, Any]]) -> None:
        centroid = self._centroid_from_sectors()
        if not centroid:
            return
        base_lat, base_lng = centroid
        for rec in rows:
            if rec.get("lat") is not None and rec.get("lon") is not None:
                continue
            rec_id = str(rec.get("id") or rec.get("url") or "")
            lat, lng = self._jitter_coords(base_lat, base_lng, rec_id) if rec_id else (base_lat, base_lng)
            rec["lat"] = round(lat, 7)
            rec["lon"] = round(lng, 7)
            rec["coord_source"] = rec.get("coord_source") or "portal_sector_centroid_jitter"

    def _attach_geometry(self, rec: dict[str, Any], text: str) -> None:
        if record_geometry(rec):
            return
        index = self._load_sector_index()
        if not index:
            return
        blob = text.upper()
        for m in RE_SECTOR_CODE.finditer(text):
            code = m.group(1).upper().replace("P_COD", "").replace("_", "").strip(" :")
            for candidate in (code, m.group(1).upper()):
                hit = index.get(candidate)
                if hit:
                    rec.update(hit)
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(hit["geom_geojson"])
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                    return
        for code, hit in index.items():
            if len(code) >= 3 and code in blob:
                rec.update(hit)
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(hit["geom_geojson"])
                if centroid:
                    rec["lat"], rec["lon"] = centroid
                return

    def _collect_normas_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normas_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pdf in self._extract_pdfs(html):
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            titulo = f"Normas subsidiarias Torrelodones: {name}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(pdf),
                    "url": self.normas_url,
                    "pdf_url": pdf,
                    "origen": "normas_subsidiarias",
                }
            )
        return rows

    def _collect_avisos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for query in self.aviso_searches:
            url = f"{WP_BASE}/wp-json/wp/v2/pages?search={urllib.parse.quote(query)}&per_page=30"
            try:
                pages = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(pages, list):
                continue
            for page in pages:
                link = str(page.get("link") or "").strip()
                if not link or link in seen_links:
                    continue
                title = _strip_html(str((page.get("title") or {}).get("rendered") or ""))
                if not RE_PROYECTO.search(title):
                    continue
                seen_links.add(link)
                content = str((page.get("content") or {}).get("rendered") or "")
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(page.get("date") or "")),
                        "url": link,
                        "pdfs": self._extract_pdfs(content),
                        "origen": "wp_aviso",
                    }
                )
        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r'<tbody[^>]*id="idd"[^>]*>(.*?)</tbody>', html, re.I | re.S)
        if not tbody_m:
            tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return rows
        for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
            row_html = row_m.group(1)
            if "emptyRow" in row_html or "preview-document" not in row_html:
                continue
            cells: dict[str, str] = {}
            doc_url = self.board_url
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls, label, val = cm.group(1), cm.group(2), cm.group(3)
                link_m = re.search(r'href="([^"]+)"', val, re.I)
                if link_m and "class_name" in cls:
                    doc_url = self._abs_url(link_m.group(1), self.sede_base)
                cells[label] = _strip_html(val)
            if not cells:
                continue
            titulo = cells.get("Descripción") or cells.get("Documento") or ""
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells.get("Expediente", ""),
                    "procedimiento": cells.get("Procedimiento", ""),
                    "categoria": cells.get("Categoría", ""),
                    "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                    "url": doc_url,
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_ssl_ctx=True)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite; no concesión publicada en tablón",
                    "origen": "urbanismo_tramite",
                }
            )
        sede_url = f"{self.sede_base}/registro"
        rows.append(
            {
                "id": _stable_id("lic", sede_url),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación trámites urbanísticos",
                "url": sede_url,
                "source": "ayuntamiento",
                "nota": "Declaración responsable, licencia obra mayor/menor, actos comunicados",
                "origen": "sede_tramites",
            }
        )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('procedimiento', '')} {row.get('categoria', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _normas_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": "planeamiento",
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec, row["titulo"])
        return rec

    def _aviso_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
        self._attach_geometry(rec, row["titulo"])
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('procedimiento', '')} {row.get('categoria', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "expte": row.get("expediente"),
            "source": "ayuntamiento",
            "origen": "sede_board",
        }
        self._attach_geometry(rec, blob)
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info_pages():
            add(rec)
        for board in self._collect_board():
            add(self._board_to_licencia(board))

        self._apply_coords_fallback(rows)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen", "").startswith(("urbanismo", "sede"))),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        for rec in self._load_jsonl(out_jsonl):
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

        for item in self._collect_normas_pdfs():
            add(self._normas_to_proyecto(item))
        for item in self._collect_avisos():
            add(self._aviso_to_proyecto(item))
        for board in self._collect_board():
            add(self._board_to_proyecto(board))

        self._apply_coords_fallback(rows)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "normas_pdfs": sum(1 for r in rows if r.get("origen") == "normas_subsidiarias"),
            "avisos": sum(1 for r in rows if r.get("origen") == "wp_aviso"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
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
