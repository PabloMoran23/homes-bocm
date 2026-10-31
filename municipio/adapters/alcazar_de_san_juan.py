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

WEB_BASE = "https://alcazardesanjuan.es"
SEDE_BASE = "https://sede.alcazardesanjuan.es"
MUNICIPIO = "Alcázar de San Juan"
ID_PREFIX = "alcazar-de-san-juan"
INE_MUN = "13005"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ordenacion-territorial-y-urbanistica/",
]

URBANISMO_KEYWORD = "PTS_PC_012"

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia urbanística",
    "licencia de obra",
    "declaración responsable",
    "declaracion responsable",
    "comunicación previa",
    "comunicacion previa",
    "primera ocupación",
    "primera ocupacion",
    "licencia de demolición",
    "licencia de parcelación",
    "licencia de reparcelación",
    "concesión de licencia",
    "concesion de licencia",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra[s]? (?:mayor|menor)|"
    r"primera ocupaci[oó]n|exposici[oó]n p[uú]blica.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio urban|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|estudio de detalle|"
    r"modificaci[oó]n|sector|dictamen.*pgou|normas.*presupuesto|actividad consistente|"
    r"integraci[oó]n de equipos|reordenar vol[uú]menes|compatibilidad urban)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"bolsa de|calificaciones|nombramiento|subvenci[oó]n|iae\b|cobranza|"
    r"autotaxi|taxi\b|notificaci[oó]n colectiva|edicto notarial)",
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(text or "")
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "exposici" in n or "informaci" in n:
        return "información pública"
    if "dictamen" in n and "pgou" in n:
        return "dictamen PGOU"
    if "plan especial" in n or "plan parcial" in n:
        return "planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "licencia" in n:
        return "licencia publicada"
    if "actividad" in n:
        return "actividad / compatibilidad"
    return "urbanismo"


class AlcazarDeSanJuanAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress transparencia + sede STA TAO (tablón/catálogo) + CLM ArcGIS PGOU (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or INE_MUN)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcazar-de-san-juan/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcazar-de-san-juan/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

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

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, timeout=90)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or "")
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "remitente": remitente,
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, timeout=60)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            keywords = item.get("keywordList") or []
            kw_codes = {str(k.get("code") or "") for k in keywords}
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                    "urbanismo_kw": URBANISMO_KEYWORD in kw_codes,
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=45)
            except urllib.error.URLError:
                continue
            for href in RE_PDF.findall(html):
                pdf = urljoin(page_url, href)
                if pdf in seen:
                    continue
                name = _clean_title(unquote(Path(pdf).name.replace("-", " ")))
                blob = f"{name} {pdf}"
                if not RE_PROYECTO.search(blob) and "pgou" not in blob.lower():
                    continue
                seen.add(pdf)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _fecha_from_blob(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _fetch_clm_pgou(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if self._pgou_geom is not None:
            return self._pgou_geom, self._pgou_meta
        where = f"COD_INE='{self.cod_ine}'"
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "NOM_PLAN,PLAN_,FECHA_APRO,DESCARGA",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            }
        )
        url = f"{self.clm_layer}/query?{params}"
        try:
            raw = self._fetch_bytes(url, timeout=90)
            data = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        features = data.get("features") or []
        if not features:
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        feat = features[0]
        geom = feat.get("geometry")
        props = feat.get("properties") or {}
        if not isinstance(geom, dict) or not geom.get("type"):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        self._pgou_geom = geom
        self._pgou_meta = {
            "nom_plan": props.get("NOM_PLAN"),
            "plan_code": props.get("PLAN_"),
            "descarga": props.get("DESCARGA"),
            "geometry_source_url": url,
        }
        return self._pgou_geom, self._pgou_meta

    def _pgou_proyecto_row(self) -> dict[str, Any] | None:
        geom, meta = self._fetch_clm_pgou()
        if not geom or not meta:
            return None
        nom = str(meta.get("nom_plan") or "Plan General de Ordenación Urbana")
        url = str(
            meta.get("descarga")
            or f"{self.web_base}/ordenacion-territorial-y-urbanistica/"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"clm-pgou:{self.cod_ine}"),
            "municipio": MUNICIPIO,
            "titulo": f"{nom} — {MUNICIPIO} (CLM)",
            "fecha": None,
            "tipo": "PGOU",
            "url": url,
            "source": "ayuntamiento",
            "origen": "clm_arcgis",
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": meta.get("geometry_source_url"),
            "coord_source": "portal_geometry_centroid",
        }
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid
        return rec

    def _attach_pgou_if_plan(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = (rec.get("titulo") or "").lower()
        if "pgou" not in blob and "plan general" not in blob:
            return
        geom, meta = self._fetch_clm_pgou()
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = (meta or {}).get("geometry_source_url")
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')} {row.get('remitente', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia|exposici", blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": row["extern"]} if row.get("extern") else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not row.get("urbanismo_kw") and not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS):
            if not RE_LICENCIA.search(titulo):
                return None
        if RE_NOISE.search(titulo) and "licencia" not in lower:
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('remitente', '')} {row.get('extern', '')}"
        is_urbanismo = "URBANISMO" in str(row.get("remitente") or "").upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not is_urbanismo and not RE_PROYECTO.search(titulo):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("extern"):
            rec["expte"] = row["extern"]
        self._attach_pgou_if_plan(rec)
        return rec

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not row.get("urbanismo_kw") and not RE_PROYECTO.search(titulo):
            return None
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": None,
            "tipo": _proyecto_tipo(titulo),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_pgou_if_plan(rec)
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._tablon_rows():
            rec = self._tablon_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._tablon_rows():
            add(self._row_to_proyecto(row))
        for row in self._collect_web_docs():
            add(self._row_to_proyecto(row))
        for row in self._catalog_rows():
            add(self._tramite_to_proyecto(row))
        add(self._pgou_proyecto_row())
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_web_clm_arcgis"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
