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

from shapely.geometry import shape

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE = "https://cieza.sedipualba.es"
MUNICIPIO = "Cieza"
ID_PREFIX = "cieza"
COD_INE = "30019"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE}/tablondeanuncios/"
CATALOGO = f"{SEDE}/catalogoservicios.aspx"
CATALOGO_PLANEAMIENTO = f"{SEDE}/catalogoservicios.aspx?area=1159&ambito=1"
CATALOGO_OBRAS = f"{SEDE}/catalogoservicios.aspx?area=1147&ambito=1"
TRANSPARENCIA = f"{SEDE}/transparencia/"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Cieza%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

RE_TRAMITE = re.compile(
    r'href="(https://cieza\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_ANUNCIO = re.compile(
    r'href="(https://cieza\.sedipualba\.es/tablondeanuncios/anuncio\.aspx\?id=\d+)"[^>]*>\s*([^<]{0,400})',
    re.I,
)
RE_DOC_LINK = re.compile(
    r'href="((?:https://cieza\.sedipualba\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|"
    r"inicio de obra|obra (?:mayor|menor)|primera ocupaci[oó]n|ocupaci[oó]n de la v[ií]a p[uú]blica|ovp)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|suelo urban|ordenanza|edicto|aprobaci[oó]n|"
    r"delimitaci[oó]n|urbanizaci[oó]n|gesti[oó]n urban|planeamiento|apr\d|sun[su]?|"
    r"extracto acuerdos.*urban|calidad urbana)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa|pleno|jgl|jurado del municipio|subvenci[oó]n|taller|licitaci[oó]n|"
    r"herederos abintestato|edicto.*recaudat|rrhh|tribunal|empadron)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBITO = re.compile(
    r"(?i)\b((?:UA|APR|SUN[SU]?|ZV|VG|EQ|QG|SNUPH|SUNS|SD|PP|SECTOR)[\s\-]?(?:\d+[\.\d]*)?(?:\s*\([A-Za-z]+\))?)\b",
)


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


def _normalize_ambito(raw: str) -> str:
    code = _clean(raw).upper()
    code = re.sub(r"\s+", "-", code)
    return code


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_AMBITO.finditer(text or ""):
        code = _normalize_ambito(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan parcial" in n or re.search(r"\bapr\d", n):
        return "plan parcial / ámbito"
    if "plan general" in n or "pgou" in n or "pgmo" in n:
        return "planeamiento general"
    if "suelo urbanizable" in n or "suns" in n or "sun-" in n:
        return "suelo urbanizable"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "licencia" in n:
        return "licencia publicada"
    if "extracto acuerdos" in n:
        return "acuerdo pleno / urbanismo"
    return "planeamiento"


def _best_geometry(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick one valid polygon per ámbito (largest area) — merging often breaks topology."""
    best: dict[str, Any] | None = None
    best_area = -1.0
    for g in geoms:
        if not isinstance(g, dict) or not g.get("type"):
            continue
        try:
            area = shape(g).area
        except Exception:
            continue
        if area > best_area and shape(g).is_valid:
            best_area = area
            best = g
    return best


class CiezaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Sedipualba (cieza.sedipualba.es) + WFS planeamiento CARM (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede = str(self.config.get("sede_base") or SEDE).rstrip("/")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None
        self._wfs_rows: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cieza/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = encoding or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede}{href if href.startswith('/') else '/' + href}"

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

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS, timeout=60, encoding="iso-8859-1")
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _collect_tablon_html(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        seeds = (
            TABLON_URL,
            f"{self.sede}/tablondeanuncios/default.aspx?area=433",
            f"{self.sede}/tablondeanuncios/default.aspx?area=428",
        )
        for url in seeds:
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            for href, title_raw in RE_ANUNCIO.findall(html):
                url_ann = href.strip()
                if url_ann in seen:
                    continue
                seen.add(url_ann)
                title = _clean(title_raw) or url_ann
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url_ann,
                        "fecha": _parse_fecha_dmy(title),
                        "origen": "tablon_html",
                    }
                )
        return rows

    def _enrich_anuncio(self, row: dict[str, Any]) -> dict[str, Any]:
        url = row.get("url") or ""
        if "anuncio.aspx" not in url:
            return row
        try:
            html = self._fetch(url, timeout=60)
        except urllib.error.URLError:
            return row
        out = dict(row)
        docs = [self._abs_sede(m.group(1)) for m in RE_DOC_LINK.finditer(html)]
        if docs:
            out["pdf_url"] = docs[0]
        fecha = _parse_fecha_dmy(html)
        if fecha:
            out["fecha"] = fecha
        blob = _clean(re.sub(r"<[^>]+>", " ", html))[:2000]
        out["blob"] = f"{out.get('titulo', '')} {blob}"
        return out

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for catalog_url in (CATALOGO_PLANEAMIENTO, CATALOGO_OBRAS, CATALOGO):
            try:
                html = self._fetch(catalog_url, timeout=60)
            except urllib.error.URLError:
                continue
            for href, title in RE_TRAMITE.findall(html):
                if href in seen:
                    continue
                seen.add(href)
                title = _clean(title)
                if not title:
                    continue
                rows.append({"titulo": title, "url": href, "origen": "sede_tramite"})
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index

        by_ambito: dict[str, list[dict[str, Any]]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url, timeout=120))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = {}
            self._wfs_rows = []
            return self._wfs_index

        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            ambito = _normalize_ambito(str(props.get("Ambito") or props.get("ambito") or ""))
            if not ambito:
                continue
            by_ambito.setdefault(ambito, []).append({"geom": geom, "props": props})

        index: dict[str, dict[str, Any]] = {}
        wfs_rows: list[dict[str, Any]] = []
        for ambito, parts in by_ambito.items():
            geom = _best_geometry([p["geom"] for p in parts if p.get("geom")])
            if not geom:
                continue
            props = parts[0]["props"]
            clas = props.get("Clasificacion") or props.get("clasificacion")
            titulo = f"Ámbito {ambito}" + (f" — {clas}" if clas else "")
            rec = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
                "clasificacion": clas,
                "titulo": titulo,
                "fecha": props.get("Fecha") or props.get("fecha"),
                "origen": "carm_wfs",
                "url": self.wfs_url,
            }
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
            index[ambito] = rec
            wfs_rows.append(rec)

        self._wfs_index = index
        self._wfs_rows = wfs_rows
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "blob", "descripcion"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            hit = index.get(code)
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "ambito",
                "clasificacion",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _info_licencias(self) -> list[dict[str, Any]]:
        centroid = self.config.get("centroid") or [38.239, -1.419]
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": MUNICIPIO,
                "lat": float(centroid[0]),
                "lon": float(centroid[1]),
                "titulo": "Tablón de anuncios — sede electrónica Cieza",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en cieza.sedipualba.es",
                "origen": "sede_tablon",
                "coord_source": "municipio_centroid",
                "coordinates_crs": "EPSG:4326",
                "coordinates_axis_order": "xy",
            },
            {
                "id": _stable_id("lic", CATALOGO_OBRAS),
                "fecha_concesion": None,
                "tipo": "catálogo trámites obras",
                "distrito": MUNICIPIO,
                "lat": float(centroid[0]),
                "lon": float(centroid[1]),
                "titulo": "Trámites Obras, Vivienda e Infraestructuras",
                "url": CATALOGO_OBRAS,
                "source": "ayuntamiento",
                "nota": "Procedimientos licencia/obra en sede Sedipualba (sin histórico de concesiones)",
                "origen": "sede_tramite",
                "coord_source": "municipio_centroid",
                "coordinates_crs": "EPSG:4326",
                "coordinates_axis_order": "xy",
            },
        ]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia / obra",
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        if rec.get("lat") is None:
            c = self.config.get("centroid") or [38.239, -1.419]
            rec["lat"], rec["lon"] = float(c[0]), float(c[1])
            rec["coord_source"] = rec.get("coord_source") or "municipio_centroid"
        rec.setdefault("coordinates_crs", "EPSG:4326")
        rec.setdefault("coordinates_axis_order", "xy")
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("pdf_url") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        if rec.get("lat") is None:
            c = self.config.get("centroid") or [38.239, -1.419]
            rec["lat"], rec["lon"] = float(c[0]), float(c[1])
            rec["coord_source"] = rec.get("coord_source") or "municipio_centroid"
        rec.setdefault("coordinates_crs", "EPSG:4326")
        rec.setdefault("coordinates_axis_order", "xy")
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("ambito") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "ambito",
            "clasificacion",
            "geom_geojson",
            "geometry_crs",
            "geometry_axis_order",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
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

        for rec in self._info_licencias():
            add(rec)
        for item in self._collect_tramites():
            add(self._tramite_to_licencia(item))
        for item in self._collect_tablon_rss() + self._collect_tablon_html():
            add(self._tablon_to_licencia(self._enrich_anuncio(item)))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

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

        self._build_wfs_index()
        for item in self._wfs_rows or []:
            add(self._to_proyecto(item))

        for item in self._collect_tablon_rss() + self._collect_tablon_html():
            add(self._tablon_to_proyecto(self._enrich_anuncio(item)))

        if not rows:
            add(
                self._to_proyecto(
                    {
                        "titulo": "Planeamiento urbanístico — visor CARM SITMURCIA",
                        "url": self.wfs_url,
                        "fecha": None,
                        "tipo": "planeamiento",
                        "origen": "carm_wfs",
                    }
                )
            )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "carm_wfs": sum(1 for r in rows if r.get("origen") == "carm_wfs"),
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
