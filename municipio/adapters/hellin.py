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
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE = "https://hellin.sedipualba.es"
WEB = "https://www.hellin.es"
MUNICIPIO = "Hellín"
ID_PREFIX = "hellin"
INE_MUN = "02037"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE}/tablondeanuncios/default.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx"

CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB}/index.php/2013-11-14-00-43-08/pet",
    f"{WEB}/index.php/2013-11-14-00-43-08/pstd",
    f"{WEB}/index.php/2013-11-14-00-45-19/tramites-electronicos",
]

RE_TRAMITE = re.compile(
    r'href="(https://hellin\.sedipualba\.es/[^"]*tramite\.aspx\?idtramite=\d+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_TABLON_ROW = re.compile(
    r'href="(https://hellin\.sedipualba\.es/tablondeanuncios/anuncio\.aspx\?id=\d+)"',
    re.I,
)
RE_DOC_LINK = re.compile(
    r'href="((?:https://hellin\.sedipualba\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra[s]? (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"fotov|instalaci[oó]n solar|sector|gesti[oó]n urban)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de trabajo|comisi[oó]n de servicios|plantilla|calificaci[oó]n|"
    r"concurso.*m[eé]ritos|proceso selectivo|auxiliar de administraci[oó]n|"
    r"ingeniero.*t[eé]cnico.*industrial|inspector.*urbanismo oep|listado.*admitidos|"
    r"modificaci[oó]n de cr[eé]ditos|suplementos de cr[eé]dito|cr[eé]ditos 3sc)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_RANGE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})")
RE_PARCELA = re.compile(r"(?i)P[º°]\s*(\d+)\s*P[ªa]\s*(\d+)")


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
    years = [
        int(y.group(1))
        for y in re.finditer(r"\b((?:19|20)\d{2})\b", text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "fotov" in n or "solar" in n:
        return "instalación fotovoltaica / IP"
    if "plan parcial" in n or "sector" in n or re.search(r"p[º°]\s*\d+", n):
        return "información pública / parcela"
    if "modific" in n:
        return "modificación planeamiento"
    if "informaci" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    return "urbanismo"


class HellinAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Joomla hellin.es + sede Sedipualba (tablón/catálogo) + CLM ArcGIS PGOU (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_TRAMITES)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 4))
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or INE_MUN)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None
        self._web_ssl: ssl.SSLContext | None = None
        if self.config.get("insecure_ssl", True):
            self._web_ssl = ssl.create_default_context()
            self._web_ssl.check_hostname = False
            self._web_ssl.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, timeout: int = 60, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-hellin/1.0")},
        )
        ctx = self._web_ssl if self._web_ssl and "hellin.es" in url else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = encoding or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-hellin/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, timeout=60)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_TRAMITE.findall(html):
            titulo = _clean(title)
            if href in seen:
                continue
            seen.add(href)
            rows.append({"titulo": titulo[:500], "url": href, "origen": "sede_tramite"})
        return rows

    def _parse_tablon_html(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            row_html = m.group(1)
            link_m = RE_TABLON_ROW.search(row_html)
            if not link_m:
                continue
            url = link_m.group(1)
            if url in seen:
                continue
            seen.add(url)
            text = _clean(re.sub(r"<[^>]+>", " ", row_html))
            fecha = None
            rng = RE_FECHA_RANGE.search(text)
            if rng:
                fecha = _parse_fecha_dmy(rng.group(1))
            title = text
            if rng:
                title = text[text.find(rng.group(0)) + len(rng.group(0)) :].strip()
            if not title:
                title = text
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": fecha,
                    "origen": "tablon_html",
                    "blob": text,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        try:
            raw = self._fetch(self.tablon_rss, timeout=60, encoding="iso-8859-1")
            root = ET.fromstring(raw.encode("latin-1", errors="replace"))
            for item in root.findall(".//item"):
                title = _clean(item.findtext("title") or "")
                link = (item.findtext("link") or "").strip()
                if not title or not link:
                    continue
                by_url[link] = {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": _parse_rss_date(item.findtext("pubDate") or ""),
                    "origen": "tablon_rss",
                    "blob": title,
                }
        except (urllib.error.URLError, ET.ParseError):
            pass
        try:
            html = self._fetch(self.tablon_url, timeout=60, encoding="latin-1")
            for row in self._parse_tablon_html(html):
                by_url.setdefault(row["url"], row)
                if row["url"] in by_url and row.get("fecha"):
                    by_url[row["url"]]["fecha"] = row["fecha"]
        except urllib.error.URLError:
            pass
        return list(by_url.values())

    def _enrich_anuncio(self, row: dict[str, Any]) -> dict[str, Any]:
        url = row.get("url") or ""
        if "anuncio.aspx" not in url:
            return row
        try:
            html = self._fetch(url, timeout=60)
        except urllib.error.URLError:
            return row
        docs = [self._abs_sede(m.group(1)) for m in RE_DOC_LINK.finditer(html)]
        out = dict(row)
        if docs:
            out["pdf_url"] = docs[0]
            out["documentos"] = docs
        fecha = _parse_fecha_dmy(html) or out.get("fecha")
        if fecha:
            out["fecha"] = fecha
        parcela = RE_PARCELA.search(out.get("titulo") or "")
        if parcela:
            out["parcela_ref"] = f"Pº{parcela.group(1)} Pª{parcela.group(2)}"
        return out

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
        url = str(meta.get("descarga") or f"{self.web_base}/index.php/2013-11-14-00-43-08/pet")
        rec: dict[str, Any] = {
            "titulo": f"{nom} — {MUNICIPIO} (CLM)",
            "fecha": None,
            "url": url,
            "tipo": "PGOU",
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
        if "pgou" not in blob and "plan general" not in blob and "ordenaci" not in blob:
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

    def _crawl_web_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.seed_pages[: self.max_crawl_pages]:
            try:
                html = self._fetch(url, timeout=12)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)", html, re.I) or re.search(
                r"<title>([^<]+)</title>", html, re.I
            )
            title = _clean(title_m.group(1)) if title_m else url.rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": _parse_fecha_dmy(html),
                    "origen": "web_portal",
                }
            )
        return rows

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
            "distrito": row.get("parcela_ref"),
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("parcela_ref"):
            rec["parcela_ref"] = row["parcela_ref"]
        if row.get("documentos"):
            rec["documentos"] = row["documentos"]
        for key in (
            "geom_geojson",
            "geometry_crs",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        if not record_geometry(rec):
            self._attach_pgou_if_plan(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        enriched = self._enrich_anuncio(row)
        return self._to_proyecto(enriched)

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        url = row.get("url") or ""
        if not RE_PROYECTO.search(blob) and not any(
            x in url for x in ("pet", "pstd", "urban", "planeam")
        ):
            return None
        rec = self._to_proyecto(row)
        self._attach_pgou_if_plan(rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        rows.append(
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón sedipualba",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios electrónico — Ayuntamiento de Hellín (Sedipualba)",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas; solo trámites y edictos",
                "origen": "sede_tablon",
            }
        )
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_tablon"}

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

        pgou = self._pgou_proyecto_row()
        if pgou:
            add(self._to_proyecto(pgou))
        for item in self._crawl_web_seeds():
            add(self._web_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "clm_pgou": 1 if pgou else 0,
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "web_portal": sum(1 for r in rows if r.get("origen") == "web_portal"),
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
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
