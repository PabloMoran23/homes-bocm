from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE = "https://caravaca.sedipualba.es"
WEB = "https://caravacadelacruz.es"
MUNICIPIO = "Caravaca de la Cruz"
ID_PREFIX = "caravaca-de-la-cruz"
COD_INE = "30008"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE}/tablondeanuncios.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx?ambito=&area=887"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Caravaca%20de%20la%20Cruz%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB}/normativa-municipal/",
    f"{WEB}/urbanismo-obras/",
    f"{WEB}/plan-general/",
    f"{WEB}/normas-y-fichas/",
    f"{WEB}/planimetria/",
    f"{WEB}/perip-avance/",
]

RE_TRAMITE = re.compile(
    r'href="(https://caravaca\.sedipualba\.es/[^"]*tramite\.aspx\?idtramite=\d+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_TABLON_ROW = re.compile(
    r'href="(https://caravaca\.sedipualba\.es/tablondeanuncios/anuncio\.aspx\?id=\d+)"',
    re.I,
)
RE_DOC_LINK = re.compile(
    r'href="((?:https://caravaca\.sedipualba\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra[s]? (?:mayor|menor)|primera ocupaci[oó]n|"
    r"certificado urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgmo|pgou|perip|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"normas y fichas|planimetr|titularidad|finca|sector|ordenanza)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"proceso selectivo|lista (?:provisional|definitiva).*admitidos|"
    r"modificaci[oó]n del presupuesto|suplemento de cr[eé]dito|transferencia de cr[eé]dito|"
    r"plantilla|pleno extraordinario|publicidad emisora|tribunal|concurso|"
    r"bolsa de|archivero|auxiliar t[eé]cnico|conserje|administrativo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_RANGE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})")
RE_AMBITO = re.compile(r"(?i)\b(UR-[A-Z0-9]+(?:\s+[A-Za-z][\w\s]*)?|SGEL[\s-]?\d+)\b")


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


def _normalize_ambito(raw: str) -> str:
    s = unescape(raw or "").strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s[:120]


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
    if "perip" in n:
        return "PERIP"
    if "plan general" in n or "pgmo" in n or "pgou" in n:
        return "PGMO"
    if "normas y fichas" in n or "planimetr" in n:
        return "documentación planeamiento"
    if "informaci" in n or "exp. p" in n:
        return "información pública"
    if "titularidad" in n:
        return "investigación titularidad"
    if "modific" in n:
        return "modificación planeamiento"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class CaravacaDeLaCruzAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress caravacadelacruz.es + sede Sedipualba + WFS SITMURCIA (partial geometry)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_TRAMITES)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = encoding or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        return out

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.seed_pages:
            try:
                html = self._fetch(url, timeout=30)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)", html, re.I) or re.search(
                r"<title>([^<]+)</title>", html, re.I
            )
            title = _clean(title_m.group(1)) if title_m else url.rstrip("/").rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": _parse_fecha_dmy(html),
                    "origen": "web_portal",
                    "blob": f"{title} planeamiento urbanismo",
                    "tipo": _proyecto_tipo(title),
                }
            )
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url, timeout=120))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
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
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
                "clasificacion": props.get("Clasificacion"),
                "ficha_url": props.get("Enlace_ficha"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[ambito] = rec
            for alt in _ambito_codes_from_text(str(props.get("Ambito") or "")):
                index.setdefault(alt, rec)
        self._wfs_index = index
        return index

    def _wfs_reference_proyectos(self) -> list[dict[str, Any]]:
        index = self._build_wfs_index()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for ambito, hit in index.items():
            if ambito in seen or not hit.get("geom_geojson"):
                continue
            seen.add(ambito)
            ficha = hit.get("ficha_url") or self.wfs_url
            rows.append(
                {
                    "titulo": f"{ambito} — {MUNICIPIO} (SITMURCIA PGMO)",
                    "fecha": None,
                    "url": str(ficha),
                    "tipo": "ámbito planeamiento",
                    "origen": "sitmurcia_wfs",
                    "geom_geojson": hit["geom_geojson"],
                    "geometry_crs": "EPSG:4326",
                    "geometry_source": hit.get("geometry_source"),
                    "geometry_source_url": hit.get("geometry_source_url"),
                    "coord_source": hit.get("coord_source"),
                    "lat": hit.get("lat"),
                    "lon": hit.get("lon"),
                    "ambito": ambito,
                }
            )
            if len(rows) >= 12:
                break
        return rows

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "blob", "ambito"))
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
                "coord_source",
                "lat",
                "lon",
                "ambito",
                "clasificacion",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

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
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or row.get("blob") or ""
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
        for key in (
            "geom_geojson",
            "geometry_crs",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "ambito",
            "clasificacion",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
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

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return self._to_proyecto(row)

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
                "titulo": "Tablón de anuncios electrónico — Caravaca de la Cruz (Sedipualba)",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas; trámites y edictos",
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

        for item in self._wfs_reference_proyectos():
            add(self._to_proyecto(item))
        for item in self._collect_web_seeds():
            add(self._web_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "sitmurcia_wfs": sum(1 for r in rows if r.get("origen") == "sitmurcia_wfs"),
            "web_portal": sum(1 for r in rows if r.get("origen") == "web_portal"),
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
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
