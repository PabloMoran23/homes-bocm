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

WEB_BASE = "https://www.pielagos.es"
MUNICIPIO = "Piélagos"
ID_PREFIX = "pielagos"
COD_INE = "39052"

TABLON_URL = f"{WEB_BASE}/tablon-de-anuncios-virtual"
PGOU_VIGENTE_URL = f"{WEB_BASE}/plan-general-de-ordenacion-vigente"
SERVICIOS_TECNICOS_URL = f"{WEB_BASE}/servicios-tecnicos"
SEDE_URL = "https://sede.pielagos.es/"
AUCAN_URL = "https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/pielagos"

WFS_BASE = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
WFS_NS = "https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer"
GML_NS = "http://www.opengis.net/gml"

DEFAULT_SEED_PAGES: list[str] = [
    PGOU_VIGENTE_URL,
    f"{WEB_BASE}/plan-general-de-ordenacion-2023",
    f"{WEB_BASE}/plan-general-de-ordenacion-2016-exposicion",
    SERVICIOS_TECNICOS_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|informaci[oó]n p[uú]blica de solicitud|"
    r"concesi[oó]n de licencia|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|municipal)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"urbanizaci[oó]n|sector|suelo|ordenanza (?:fiscal|reguladora)|"
    r"exposici[oó]n p[uú]blica|expropiaci|consulta previa|"
    r"liencres|parbay[oó]n|yesera|cierro de la sara)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|funcionario|promoci[oó]n interna|becas|"
    r"guarder[ií]a|ludoteca|catering social|atenci[oó]n domiciliaria|"
    r"padr[oó]n del precio|padr[oó]n de las tasas|liquidaciones de valores|"
    r"impuesto de actividades|\biae\b|escuela municipal de|"
    r"gratuidad de libros|delegaci[oó]n de atribuciones|"
    r"enajenaci[oó]n de bien patrimonial|correcci[oó]n de errores al anuncio|"
    r"convocatoria.*plaza|empleo p[uú]blico)",
)
RE_TABLON_ROW = re.compile(
    r'<td[^>]*text-align:center[^>]*>\s*(\d{2}-\d{2}-\d{4})\s*</td>\s*'
    r'<td[^>]*text-align:justify[^>]*>(.*?)</td>',
    re.S | re.I,
)
RE_TABLON_LINK = re.compile(
    r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
RE_FECHA_PUB = re.compile(
    r"publicado el\s+(\d{1,2})\s+de\s+("
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre"
    r")\s+de\s+(\d{4})",
    re.I,
)
RE_FECHA_YM = re.compile(r"/(?:uploads|data)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:Expediente|Expte\.?)\s+(\d{4}/\d+|\d{1,4}/\d{2,4})"
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?pielagos\.(?:es|com))?/[^"\']+\.(?:pdf|PDF|zip)[^"\']*)["\']',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"SECTOR\s+\d+|"
    r"SUNP-\d+|"
    r"SUP-\d+|"
    r"Cierro de Sara|La Joya|El Cuco|Alto del Cuco|"
    r"Torre de Velo|Ropesa|Sorribero|Yesera|Liencres|Parbay[oó]n"
    r")\b",
)
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy_dash(text: str) -> str | None:
    m = RE_FECHA_DMY_DASH.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_publicado(text: str) -> str | None:
    m = RE_FECHA_PUB.search(text or "")
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    for parser in (_parse_fecha_dmy_dash, _parse_fecha_publicado, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    m = re.match(r"SECTOR\s+(\d+)", code)
    if m:
        return f"SECTOR {m.group(1)}"
    m = re.match(r"SUNP-(\d+)", code)
    if m:
        return f"SUNP-{m.group(1)}"
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
    if "expropiaci" in n:
        return "expropiación forzosa"
    if "plan municipal de obras" in n:
        return "plan municipal de obras"
    if "plan parcial" in n or "el somo" in n:
        return "plan parcial"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "licencia" in n and "actividad" in n:
        return "licencia de actividad"
    if "primera ocupaci" in n:
        return "licencia de primera ocupación"
    if "autorizaci" in n:
        return "autorización urbanística"
    if "sector" in n:
        return "sector"
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


class PielagosAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS pielagos.es (tablón tabla + PGOU) + SIUCAN WFS Cantabria (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_VIGENTE_URL)
        self.servicios_tecnicos_url = str(
            self.config.get("servicios_tecnicos_url") or SERVICIOS_TECNICOS_URL
        )
        self.sede_url = str(self.config.get("sede_url") or SEDE_URL)
        self.aucan_url = str(self.config.get("aucan_url") or AUCAN_URL)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_sector_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pielagos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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
            tokens = [
                str(rec.get("sector_code") or ""),
                str(rec.get("sector_name") or ""),
                str(rec.get("titulo") or ""),
            ]
            for token in tokens:
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
            if ine != self.cod_ine and mun != MUNICIPIO:
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
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "origen": "siucan_wfs",
                "sector_code": sector_code or None,
                "sector_name": sector_name or None,
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                rec["coordinates_crs"] = "EPSG:4326"
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
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "coordinates_crs",
                "lat",
                "lon",
                "sector_code",
                "sector_name",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            fecha_raw = m.group(1)
            body = m.group(2)
            titulos: list[str] = []
            pdfs: list[str] = []
            link_url: str | None = None
            for link_m in RE_TABLON_LINK.finditer(body):
                href = link_m.group(1)
                text = _strip_html(link_m.group(2))
                abs_href = self._abs_web(href)
                if text:
                    titulos.append(text)
                if not link_url:
                    link_url = abs_href
                if ".pdf" in abs_href.lower():
                    pdfs.append(abs_href)
            titulo = " ".join(titulos)[:500] if titulos else _strip_html(body)[:500]
            if not titulo or len(titulo) < 15:
                continue
            blob = titulo
            if RE_EXCLUDE.search(blob):
                continue
            exp_m = RE_EXPEDIENTE.search(blob)
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _parse_fecha_dmy_dash(fecha_raw) or _fecha_from_blob(blob),
                    "url": link_url or self.tablon_url,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "pdf_urls": pdfs,
                    "expte": exp_m.group(1) if exp_m else None,
                    "blob": blob,
                    "origen": "cms_tablon",
                }
            )
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_web(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                name = re.sub(r"\.(pdf|zip)$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                rows.append(
                    {
                        "titulo": f"PGOU Piélagos — {name}"[:500],
                        "fecha": _fecha_from_blob(pdf),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "cms_pgou_pdf",
                    }
                )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('expte', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and "informaci" not in blob.lower() and "exposici" not in blob.lower():
            if "ordenanza" not in blob.lower() and "plan" not in blob.lower() and "sector" not in blob.lower():
                return None
        key = row.get("pdf_url") or row.get("expte") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or self.tablon_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('expte', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        key = row.get("expte") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.tablon_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (self.pgou_url, "PGOU vigente y planos"),
            (self.servicios_tecnicos_url, "servicios técnicos — licencias y calificación"),
            (self.tablon_url, "tablón de anuncios virtual"),
            (self.sede_url, "sede electrónica — trámites urbanísticos"),
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
                    "origen": "cms_tramite",
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
        for item in self._collect_tablon():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "cms_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "cms_tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
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

        for item in self._collect_tablon():
            add(self._row_to_proyecto(item))
        for item in self._collect_urbanismo_pdfs():
            add(self._row_to_proyecto(item))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "cms_tablon": sum(1 for r in rows if r.get("origen") == "cms_tablon"),
            "cms_pgou_pdf": sum(1 for r in rows if r.get("origen") == "cms_pgou_pdf"),
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
