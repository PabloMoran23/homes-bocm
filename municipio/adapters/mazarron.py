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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.mazarron.es"
SEDE_BASE = "https://sede.mazarron.es"
MUNICIPIO = "Mazarrón"
ID_PREFIX = "mazarron"
COD_INE = "30027"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    f"{WEB_BASE}/es/infraestructuras-y-urbanismo/planes/",
    f"{WEB_BASE}/es/infraestructuras-y-urbanismo/convenios/",
    f"{WEB_BASE}/es/infraestructuras-y-urbanismo/licencias-urbanisticas/",
    f"{WEB_BASE}/es/ayuntamiento/tramites-y-servicios/urbanismo/",
)

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Mazarr%C3%B3n%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"certificado.*urban|subrogaci[oó]n de expedientes de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgmo|pgmou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio de detalle|sector|s[\s._-]?0?3[\s._-]\d|"
    r"expropiaci[oó]n|operaci[oó]n jur[ií]dica|programa de actuaci|unidad de actuaci|"
    r"ordenaci[oó]n|suelo|demarcaci[oó]n de costas)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(jurado del municipio|lista definitiva de candidatos|baja de personas|"
    r"padrones?|notificaci[oó]n decreto 2026|estad[ií]stica|proceso selectivo|"
    r"subvenci[oó]n|empleo p[uú]blico|mercado semanal)",
)
RE_WEB_PATH = re.compile(
    r'href="(/es/infraestructuras-y-urbanismo/(?:planes|convenios)/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_S = re.compile(r"(?i)S[\s._-]?0?3[\s._-](\d{2})")
RE_AREA_A = re.compile(r"(?i)A[\s._-]?05[\s._-]01(?:/(\d{2}))?")
RE_SGEL = re.compile(r"(?i)SGEL[\s._-]?0?(\d+)")


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
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _slug_to_title(path: str) -> str:
    slug = path.rstrip("/").split("/")[-1]
    return unescape(slug.replace("-", " ")).strip()[:500]


def _sector_keys_from_ambito(ambito: str) -> list[str]:
    keys: list[str] = []
    for m in RE_SECTOR_S.finditer(ambito or ""):
        keys.append(f"S_03-{m.group(1)}")
    for m in RE_AREA_A.finditer(ambito or ""):
        suffix = m.group(1)
        keys.append(f"A_05-01/{suffix}" if suffix else "A_05-01")
    for m in RE_SGEL.finditer(ambito or ""):
        keys.append(f"SGEL-{m.group(1)}")
    return keys


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    blob = text or ""

    def add(code: str) -> None:
        c = code.upper().replace(" ", "")
        if c and c not in seen:
            seen.add(c)
            out.append(c)

    for m in RE_SECTOR_S.finditer(blob):
        add(f"S_03-{m.group(1)}")
    for m in RE_AREA_A.finditer(blob):
        add(f"A_05-01/{m.group(1)}" if m.group(1) else "A_05-01")
    for m in RE_SGEL.finditer(blob):
        add(f"SGEL-{m.group(1)}")

    low = blob.lower()
    if "volamar" in low:
        add("S_03-06")
        add("S_03-16")
    if re.search(r"(?i)\bel\s+faro\b", blob):
        add("S_03-08")
    if "castellar" in low and "ii" in low:
        add("S_03-19")
    if "playa grande" in low:
        add("S_03-14")
    if "saladillo" in low or "camposol" in low:
        add("A_05-01/04")
        add("A_05-01")
    if "rihuete" in low:
        add("A_05-01/04")
    return out


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b or re.search(r"s[\s._-]?0?3[\s._-]\d", b):
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "informaci" in b or "exposici" in b:
        return "información pública"
    if "reparcel" in b:
        return "reparcelación"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "pgmo" in b or "plan general" in b:
        return "PGMO"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class MazarronAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCms mazarron.es (planes/convenios) + sede STA tablón/catálogo + WFS SITMURCIA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mazarron/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start)
        if end < 0:
            return []
        try:
            data = json.loads(html[start : end + 1])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

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

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _strip_html(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or "")
            blob = f"{titulo} {remitente} {item.get('externString') or ''}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "origen": "tablon_sta",
                    "blob": blob,
                    "remitente": remitente,
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _strip_html(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or "")
            if not name or not dboid:
                continue
            blob = name
            is_lic = bool(RE_LICENCIA.search(blob))
            is_proy = bool(RE_PROYECTO.search(blob))
            if not is_lic and not is_proy:
                if not re.search(r"(?i)urban|infracci", blob):
                    continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": None,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_sta",
                    "blob": blob,
                    "es_tramite_licencia": is_lic,
                    "es_tramite_proyecto": is_proy,
                }
            )
        return rows

    def _collect_web_planeamiento(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_WEB_PATH.findall(html):
                url = urljoin(self.web_base, unescape(href))
                if url in seen:
                    continue
                seen.add(url)
                titulo = _slug_to_title(href)
                blob = f"{titulo} {href}"
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "origen": "web_planeamiento",
                        "blob": blob,
                    }
                )
            if "licencias-urbanisticas" in page_url:
                rows.append(
                    {
                        "titulo": "Licencias urbanísticas — información y modelos",
                        "fecha": None,
                        "url": page_url,
                        "origen": "web_licencias_info",
                        "blob": "licencias urbanísticas obra mayor",
                        "es_licencia_info": True,
                    }
                )
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            ambito = str(props.get("Ambito") or "")
            rec = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito[:200],
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            keys = {ambito.strip()} | set(_sector_keys_from_ambito(ambito))
            for key in keys:
                norm = re.sub(r"\s+", "", key.upper())
                if norm and norm not in index:
                    index[norm] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "blob"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            key = re.sub(r"\s+", "", code.upper())
            hit = index.get(key)
            if not hit:
                continue
            for field in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "ambito",
                "clasificacion",
            ):
                if hit.get(field) is not None:
                    rec[field] = hit[field]
            return

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
            return None
        if raw.get("es_tramite_proyecto") and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.web_base)
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
        if raw.get("remitente"):
            rec["remitente"] = raw["remitente"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if raw.get("es_licencia_info") or raw.get("es_tramite_licencia"):
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob) and not raw.get("es_tramite_licencia"):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or f"{self.web_base}/es/infraestructuras-y-urbanismo/licencias-urbanisticas/")
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
        if rec.get("lat") is None or rec.get("lon") is None:
            centroid = self.config.get("centroid") or [37.599, -1.314]
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = "municipio_centroid"
        rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for src in (
            self._collect_web_planeamiento(),
            self._collect_tablon(),
            self._collect_catalog_tramites(),
        ):
            for raw in src:
                rec = self._to_proyecto(raw)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources = (
            self._collect_tablon()
            + self._collect_catalog_tramites()
            + self._collect_web_planeamiento()
        )
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
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
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
            "web": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
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
