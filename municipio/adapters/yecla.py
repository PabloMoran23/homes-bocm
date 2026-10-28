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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://yecla.es"
SEDE_BASE = "https://yecla.sedipualba.es"
OV_FORMS = "https://ov.yecla.es/WebOFICINAVIRTUAL/Vista/Paginas/WebFormTramite.aspx?T=35"
MUNICIPIO = "Yecla"
ID_PREFIX = "yecla"
COD_INE = "30073"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/default.aspx?pub=false"
CATALOGO_URBANISMO = f"{SEDE_BASE}/catalogoservicios.aspx?area=589&ambito=1"
PGOU_PAGE = f"{WEB_BASE}/obras-y-urbanismo/plan-general-de-ordenacion-urbana/"
URBANISMO_PAGE = f"{WEB_BASE}/obras-y-urbanismo/"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Yecla%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|pmh|boii|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|expte|proyecto|"
    r"modificaci[oó]n|edicto|borm|tramitaci[oó]n auton[oó]mica|pmh|boii|suplemento|"
    r"ordenanza|sector|suelo|pgmo)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"certijunta|acta n[ºo°]?\s*\d+ jgl|junta de gobierno|herederos abintestato|"
    r"dominio para la inmatriculaci|cobranza.*padrones|censo electoral|"
    r"pleno extraordinario|auxiliar hogar|director escuela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_RANGE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})",
)
RE_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]*)', re.I)
RE_ANUNCIO_BLOCK = re.compile(
    r'anuncio\.aspx\?id=(\d+)[\s\S]{0,600}?alt="([^"]+)"',
    re.I,
)
RE_CODE = re.compile(
    r"(?i)\b(SUPI-\d+|SUNP[A-Z]-[\w\s]+|SNU[\w-]*|UA-\d+|SECTOR\s+\d+[-\w]*)\b",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_RANGE.search(text or "")
    if m:
        text = m.group(1)
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(y.group(1))
        for y in re.finditer(r"\b((?:19|20)\d{2})\b", text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "borm" in b and "tramitaci" in b:
        return "tramitación autonómica / BORM"
    if "pmh" in b or "boii" in b:
        return "expediente urbanístico (PMH/BOII)"
    if "exposici" in b and "p" in b and "blica" in b:
        return "exposición pública"
    if "edicto" in b:
        return "edicto"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _norm_key(text: str) -> str:
    t = unescape(text or "").upper()
    t = re.sub(r"[^A-Z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class YeclaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress yecla.es + sede Sedipualba (tablón) + OV formularios + SITMURCIA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_urbanismo = str(self.config.get("catalogo_urbanismo") or CATALOGO_URBANISMO)
        self.pgou_page = str(self.config.get("pgou_page") or PGOU_PAGE)
        self.urbanismo_page = str(self.config.get("urbanismo_page") or URBANISMO_PAGE)
        self.ov_forms_url = str(self.config.get("ov_forms_url") or OV_FORMS)
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-yecla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        if latin1:
            return raw.decode("latin-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

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

    def _collect_tablon_html(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for anuncio_id, title in RE_ANUNCIO_BLOCK.findall(html):
            titulo = unescape(title).strip()
            url = f"{self.sede_base}/tablondeanuncios/anuncio.aspx?id={anuncio_id}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": None,
                    "origen": "tablon_html",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, latin1=True)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate") or ""
            if not title or not link:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": _parse_rss_date(pub),
                    "origen": "tablon_rss",
                    "blob": title,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in self._collect_tablon_html() + self._collect_tablon_rss():
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            out.append(row)
        return out

    def _collect_pgou_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in (self.pgou_page, self.urbanismo_page):
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for href, title in RE_LINK.findall(html):
                if not href.lower().endswith(".pdf"):
                    continue
                url = self._abs_web(href)
                if url in seen:
                    continue
                seen.add(url)
                titulo = _strip_html(title) or Path(unescape(href)).name
                blob = f"{titulo} {url}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(blob),
                        "origen": "web_pgou",
                        "blob": blob,
                    }
                )
        return rows

    def _licencia_info_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos electrónicos — Yecla",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.ov_forms_url),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Oficina Virtual — formularios Obras y Urbanismo",
                "url": self.ov_forms_url,
                "source": "ayuntamiento",
                "origen": "ov_formularios",
            },
            {
                "id": _stable_id("lic", self.catalogo_urbanismo),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede — área Urbanismo y Actividades (sin trámites electrónicos listados)",
                "url": self.catalogo_urbanismo,
                "source": "ayuntamiento",
                "origen": "sede_catalogo",
            },
        ]

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
            ambito = str(props.get("Ambito") or "").strip()
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
            }
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
            keys = {_norm_key(ambito)}
            for m in RE_CODE.finditer(ambito):
                keys.add(_norm_key(m.group(1)))
            for key in keys:
                if key and key not in index:
                    index[key] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "blob"))
        blob_key = _norm_key(blob)
        index = self._build_wfs_index()
        for code in RE_CODE.findall(blob):
            hit = index.get(_norm_key(code))
            if hit:
                self._merge_geom(rec, hit)
                return
        best: tuple[int, dict[str, Any]] | None = None
        for key, hit in index.items():
            if len(key) < 6:
                continue
            if key in blob_key:
                score = len(key)
                if best is None or score > best[0]:
                    best = (score, hit)
        if best:
            self._merge_geom(rec, best[1])

    @staticmethod
    def _merge_geom(rec: dict[str, Any], hit: dict[str, Any]) -> None:
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

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_TABLON_SKIP.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        url = str(raw.get("url") or self.urbanismo_page)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": str(raw.get("titulo") or "")[:500],
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        url = str(raw.get("url") or self.tablon_url)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": "licencia / expediente tablón",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": str(raw.get("titulo") or "")[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._licencia_info_rows():
            seen.add(rec["id"])
            rows.append(rec)
        for raw in self._collect_tablon():
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon_html", "tablon_rss")),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        for raw in self._collect_tablon() + self._collect_pgou_docs():
            rec = self._to_proyecto(raw)
            if rec:
                by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "pgou_docs": sum(1 for r in rows if r.get("origen") == "web_pgou"),
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
