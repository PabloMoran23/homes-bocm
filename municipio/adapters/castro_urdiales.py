from __future__ import annotations

import hashlib
import json
import re
import ssl
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

WEB_BASE = "https://www.castro-urdiales.net"
SEDE_BASE = "https://sedeelectronica.castro-urdiales.net"
MUNICIPIO = "Castro-Urdiales"
ID_PREFIX = "castro-urdiales"
COD_INE = "39020"

URBANISMO_URL = f"{WEB_BASE}/servicios.aspx?vista=servicios-ciudadania&cod=urbanismo"
AUCAN_URL = "https://aplicacionesweb.cantabria.es/aucan/public/zona/costaoriental/castrourdiales"
WFS_BASE = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
WFS_NS = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
GML_NS = "http://www.opengis.net/gml"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WEB_BASE}/servicios-ciudadania/informacion/instrumentos-urbanisticos-existentes-vigentes",
    f"{WEB_BASE}/servicios-ciudadania/informacion/catalogos-urbanisticos",
    f"{WEB_BASE}/servicios-ciudadania/informacion/pmus",
    f"{WEB_BASE}/servicios-ciudadania/informacion/cartografia-ortofotos",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|informaci[oó]n p[uú]blica de solicitud|"
    r"concesi[oó]n de licencia|obra (?:mayor|menor)|solicitud de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|movilidad)|pgou|pmus|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"urbanizaci[oó]n|sector|unidad de ejecuci[oó]n|ordenanza (?:fiscal|reguladora)|"
    r"exposici[oó]n p[uú]blica|instrumento urban|cat[aá]logo|sunp|sup-|sup\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|funcionario|promoci[oó]n interna|becas|"
    r"convocatoria.*plaza|empleo p[uú]blico|subvenciones.*cultur|mercado navide|"
    r"luto oficial|impuesto sobre bienes|plan corresponsables|orines de perro)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PAGE = re.compile(
    r"class=['\"]color-gray text-italic[^'\"]*['\"]>(\d{1,2}/\d{1,2}/\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(r"(?i)\b(?:EXPEDIENTE|URB/)\s*(\d{1,4}/\d{2,4})\b")
RE_DOWNLOAD = re.compile(
    r"<a\s+title=['\"]([^'\"]*)['\"]\s+href=(https?://[^\s>]+)[^>]*>\s*<span>([^<]*)</span>",
    re.I | re.S,
)
RE_STRIP_LINK = re.compile(
    r"<a\s+href=(/servicios-ciudadania/informacion/[^\s>]+)[^>]*>([^<]+)</a>",
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(SUNP|SUD|SUP|SUNC|SUD)[-\s.]?\d+[A-Z0-9-]*\b",
)


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


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "-", code)
    code = code.replace(".", "-")
    return code.strip("-")


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(0))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "pmus" in n or "movilidad urbana" in n:
        return "PMUS"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "catálogo" in n or "catalogo" in n:
        return "catálogo urbanístico"
    if "sector" in n or re.search(r"\bsunp|\bsup\b", n):
        return "sector urbanístico"
    if "instrumento" in n:
        return "instrumento urbanístico"
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


class CastroUrdialesAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS ASP.NET castro-urdiales.net + sede Maggioli ATM + SIUCAN WFS Cantabria."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.aucan_url = str(self.config.get("aucan_url") or AUCAN_URL)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_sector_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        ctx = self._ssl_ctx if use_sede_ssl or "sedeelectronica.castro-urdiales.net" in url else None
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castro-urdiales/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        href = unescape(href).strip()
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.web_base}/", href.lstrip("/"))

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
            if ine != self.cod_ine and mun.replace("-", " ") not in (MUNICIPIO, "Castro Urdiales"):
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
                "sector_code": sector_code or None,
                "sector_name": sector_name or None,
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_axis_order"] = "xy"
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        self._wfs_cache = rows
        return rows

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
                "geometry_crs",
                "geometry_axis_order",
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

    def _page_fecha(self, html: str) -> str | None:
        m = RE_FECHA_PAGE.search(html or "")
        if m:
            return _parse_fecha_dmy(m.group(1))
        return _fecha_from_blob(html[:8000])

    def _collect_download_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        pages = list(self.seed_pages)
        try:
            html_urb = self._fetch(self.urbanismo_url)
            for m in RE_STRIP_LINK.finditer(html_urb):
                path, label = m.group(1), _strip_html(m.group(2))
                if any(
                    k in label.lower()
                    for k in ("instrumento", "catalogo", "catálogo", "cartograf", "pmus", "licencia", "urban")
                ):
                    pages.append(self._abs_web(path))
        except urllib.error.URLError:
            pass

        for page_url in dict.fromkeys(pages):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_fecha = self._page_fecha(html)
            for m in RE_DOWNLOAD.finditer(html):
                title = unescape(m.group(1) or m.group(3)).strip()
                pdf_url = m.group(2).strip()
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)
                if not title:
                    title = Path(urllib.parse.urlparse(pdf_url).path).name
                exp_m = RE_EXPEDIENTE.search(title)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": page_fecha or _fecha_from_blob(pdf_url + " " + title),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "expte": exp_m.group(1) if exp_m else None,
                        "origen": "web_download",
                    }
                )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('expte', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        key = row.get("pdf_url") or row.get("expte") or row["titulo"]
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
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        info: list[tuple[str, str]] = [
            (self.urbanismo_url, "Servicios Técnicos — urbanismo y licencias"),
            (self.sede_base + "/", "Sede electrónica — expedientes en exposición pública"),
            (self.aucan_url, "AUCAN — PGOU Castro-Urdiales (Gob. Cantabria)"),
        ]
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.urbanismo_url)
            for m in RE_STRIP_LINK.finditer(html):
                path, label = m.group(1), _strip_html(m.group(2))
                if RE_LICENCIA.search(label):
                    info.append((self._abs_web(path), label[:200]))
        except urllib.error.URLError:
            pass
        seen: set[str] = set()
        for url, tipo in info:
            rid = _stable_id("lic", url)
            if rid in seen:
                continue
            seen.add(rid)
            rows.append(
                {
                    "id": rid,
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "web_tramite",
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_wfs_proyectos():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_download_docs():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok" if rows else "empty",
            "source": "web_wfs",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), **result}, ensure_ascii=False),
            encoding="utf-8",
        )
        return result

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "web_tramite"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_licencias(out_jsonl)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), **result}, ensure_ascii=False),
            encoding="utf-8",
        )
        return result
