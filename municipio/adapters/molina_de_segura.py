from __future__ import annotations

import hashlib
import json
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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://sedeelectronica.molinadesegura.es"
STA_BASE = "https://cciudadana.molinadesegura.es"
URBANISMO_BASE = "https://urbanismo.molinadesegura.es"
PORTAL_BASE = "https://portal.molinadesegura.es"
MUNICIPIO = "Molina de Segura"
ID_PREFIX = "molina-de-segura"
COD_INE = "30027"

INFO_URBANISTICA_URL = f"{SEDE_BASE}/informacion-urbanistica/"
TABLON_URL = f"{STA_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON"
CATALOGO_URL = f"{STA_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
TRAMITES_URL = f"{SEDE_BASE}/tramitesyservicios/"
PGMO_URL = f"{URBANISMO_BASE}/pgmo/"

WFS_BASE = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Molina%20de%20Segura%27"
    "&outputFormat=application/json&srsName=EPSG:4326"
)

ARCHIVE_PREFIX = "https://web.archive.org/web/2id_/"

LICENCIA_TRAMITE_SLUGS: tuple[tuple[str, str], ...] = (
    ("licencia-urbanistica-obra-mayor", "Licencia urbanística (obra mayor)"),
    ("licencia-de-segregacion", "Licencia de segregación"),
    ("comunicacion-previa-en-materia-de-urbanismo", "Comunicación previa en materia de urbanismo"),
    ("declaracion-responsable-en-materia-de-urbanismo", "Declaración responsable en materia de urbanismo"),
    ("certificado-urbanistico-cedula-urbanistica", "Certificado urbanístico (cédula urbanística)"),
    ("certificado-de-uso-y-compatibilidad-urbanistica", "Certificado de uso y compatibilidad urbanística"),
    ("autorizacion-de-obras-en-la-via-publica", "Autorización de obras en la vía pública"),
)

RE_INFO_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>"
    r".*?href=\"([^\"]+)\"[^>]*>\s*DESCARGAR",
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|obra)|obra (?:mayor|menor)|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|expropiaci[oó]n|sector|borm|estatutos|anejo|memoria|planos)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(proceso selectivo|convocatoria.*empleo|subvenci[oó]n|nombramiento|"
    r"empleo p[uú]blico|pad[ró]n|tributos|recibo)",
)
RE_FECHA_PREFIX = re.compile(r"\((\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\)")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*([0-9]{4}/[0-9]+|[0-9]+/[0-9]{4}-[0-9]+)",
)
RE_AMBITO = re.compile(
    r"(?i)\b(?:SGEL(?:-[A-Z0-9]+)?|UAR-[A-Z0-9]+|UAT-[A-Z0-9]+|UAI-[A-Z0-9]+|UAU-[A-Z0-9]+|"
    r"PER-[A-Z0-9]+|API-[A-Z0-9]+(?:-[A-Z0-9]+)?|ZI\d+-M\d+|ZR\d+-[A-Z0-9]+|ZDT-M\d+|ZDG-M\d+|"
    r"ZEP-[A-Z0-9]+|CN-\d+[A-Z]?)\b",
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


def _parse_fecha_prefix(text: str) -> str | None:
    m = RE_FECHA_PREFIX.search(text or "")
    if not m:
        return None
    raw = m.group(1)
    if "-" in raw and len(raw) == 10 and raw[4] == "-":
        return raw
    parts = re.split(r"[-/]", raw)
    if len(parts) == 3:
        try:
            if len(parts[0]) == 4:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2])).strftime("%Y-%m-%d")
            return datetime(int(parts[2]), int(parts[1]), int(parts[0])).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _fecha_from_blob(text: str) -> str | None:
    for fn in (_parse_fecha_prefix, _parse_fecha_dmy):
        d = fn(text)
        if d:
            return d
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_ambito(raw: str) -> str:
    s = unescape(raw or "").strip().upper()
    s = re.split(r"[.,;]", s, maxsplit=1)[0].strip()
    s = re.sub(r"\s+", "-", s)
    return s


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_AMBITO.finditer(text or ""):
        code = _normalize_ambito(m.group(0))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "expropiaci" in b:
        return "expropiación"
    if "reparcel" in b:
        return "reparcelación"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b or "peri" in b or "per-" in b:
        return "plan especial"
    if "modificaci" in b:
        return "modificación PGMO"
    if "informaci" in b or "borm" in b:
        return "información pública"
    if "pgmo" in b:
        return "PGMO"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


class MolinaDeSeguraAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede WP (información urbanística) + STA cciudadana + PGMO + SITMURCIA WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sta_base = str(self.config.get("sta_base") or STA_BASE).rstrip("/")
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.info_url = str(self.config.get("info_url") or INFO_URBANISTICA_URL)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.wfs_base = str(self.config.get("wfs_url") or WFS_BASE).split("&count=")[0].split("&startIndex=")[0]
        self.archive_fallback = bool(self.config.get("archive_fallback", True))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, archive_on_fail: bool | None = None) -> str:
        if archive_on_fail is None:
            archive_on_fail = self.archive_fallback
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-molina-de-segura/1.0")},
        )
        ctx = self._ssl_ctx if "molinadesegura.es" in url else None
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if archive_on_fail and url.startswith("https://") and "web.archive.org" not in url:
                return self._fetch(ARCHIVE_PREFIX + url, archive_on_fail=False)
            raise
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        return json.loads(self._fetch(url))

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

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _abs_sede(self, href: str) -> str:
        return urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_info_urbanistica(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.info_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for tema, denom, detalle, href in RE_INFO_ROW.findall(html):
            tema_t = _strip_html(tema)
            denom_t = _strip_html(denom)
            detalle_t = _strip_html(detalle)
            if not denom_t and not detalle_t:
                continue
            doc_url = self._abs_sede(href) if not href.startswith("http") else unescape(href)
            if not doc_url.startswith("http"):
                doc_url = self._abs_sede(doc_url)
            blob = f"{tema_t} {denom_t} {detalle_t}"
            titulo = denom_t if len(denom_t) > 10 else f"{denom_t} — {detalle_t}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(f"{denom_t} {detalle_t}"),
                    "url": doc_url,
                    "origen": "info_urbanistica_sede",
                    "blob": blob,
                    "tema": tema_t,
                    "detalle": detalle_t[:300],
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for name in ("TABLON", "PTS2_TABLON"):
            for item in self._extract_sta_dataset(html, name):
                dboid = str(item.get("dboid") or "")
                titulo = _strip_html(str(item.get("descriptionProc") or item.get("externString") or ""))
                if not titulo or not dboid:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _xml_date(item.get("pubDateIni")),
                        "url": f"{self.tablon_url}#dboid={dboid}",
                        "origen": "tablon_sta",
                        "blob": f"{titulo} {item.get('externString') or ''}",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug, label in LICENCIA_TRAMITE_SLUGS:
            url = f"{self.sede_base}/{slug.strip('/')}/"
            rows.append(
                {
                    "titulo": label,
                    "fecha": None,
                    "url": url,
                    "origen": "catalogo_tramites",
                    "blob": label,
                    "es_licencia": True,
                }
            )
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        start = 0
        step = 200
        while True:
            url = f"{self.wfs_base}&count={step}&startIndex={start}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                break
            features = data.get("features") or []
            if not features:
                break
            for feat in features:
                props = feat.get("properties") or {}
                ambito = _normalize_ambito(str(props.get("Ambito") or ""))
                geom = feat.get("geometry")
                if not ambito or not isinstance(geom, dict):
                    continue
                rec = {
                    "geom_geojson": geom,
                    "geometry_crs": "EPSG:4326",
                    "geometry_axis_order": "xy",
                    "geometry_source": "portal_wfs",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                    "ambito": ambito,
                    "clasificacion": props.get("Clasificacion"),
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
                index[ambito] = rec
                for alt in _ambito_codes_from_text(str(props.get("Ambito") or "")):
                    index.setdefault(alt, rec)
            if len(features) < step:
                break
            start += step
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "detalle", "blob", "tema"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            hit = index.get(code)
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "geometry_crs",
                "geometry_axis_order",
                "coord_source",
                "lat",
                "lon",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            if record_geometry(rec):
                return

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.info_url)
        expte_m = RE_EXPEDIENTE.search(blob)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1).strip()
        if raw.get("detalle"):
            rec["descripcion"] = raw["detalle"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not raw.get("es_licencia") and not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or TRAMITES_URL)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob) or "1970-01-01",
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
        }
        self._attach_geometry(rec)
        centroid = self.config.get("centroid") or [38.10506, -1.20726]
        if rec.get("lat") is None or rec.get("lon") is None:
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = rec.get("coord_source") or "municipio_centroid"
        rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_info_urbanistica() + self._collect_tablon():
            rec = self._to_proyecto(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources = self._collect_tablon() + self._collect_licencia_tramites()
        for raw in sources:
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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
        return {**stats, "added": max(0, after - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyecto_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info_urbanistica": sum(1 for r in rows if r.get("origen") == "info_urbanistica_sede"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
        return {**stats, "added": max(0, after - before)}
