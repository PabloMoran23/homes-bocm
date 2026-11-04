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
from municipio.onboarding_snapshot import reviewed_records

WEB_BASE = "https://calahorra.es"
SEDE_BASE = "https://sede.calahorra.es"
MUNICIPIO = "Calahorra"
ID_PREFIX = "calahorra"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
WFS_INSTRUMENTOS_URL = (
    "https://gis.calahorra.es/geoserver/calahorra_urban_city_instrumentos/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=calahorra_urban_city_instrumentos:instrumentos"
    "&outputFormat=application/json&srsName=EPSG:4326&count=500"
)

DOCUMENTO_SITEMAPS = ("documento-sitemap.xml", "documento-sitemap2.xml")

RE_DOC_PATH = re.compile(
    r"(?i)(modificaci|pgm|plan-parcial|plan-general|convenio-urban|proyecto-de-urbaniz|"
    r"interpretaci|planeam|sector-s-|/ue-|reparcel|estudio-de-detalle|"
    r"plan-de-movilidad-urbana|ambitosplanificacion)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"parcelaci[oó]n|cedula urban|c[eé]dula urban|vado|gr[uú]a de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgm|convenio urban|"
    r"informaci[oó]n p[uú]blica|modificaci[oó]n puntual|unidad de ejecuci|"
    r"proyecto de urbaniz|interpretaci[oó]n.*pgm|sector s-|instrumento de planeamiento|"
    r"licencia conjunta ambiental y de obras|exp:\s*[\d/]+-ur)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(proceso selectivo|subvenci[oó]n|taxi|jurado del municipio|"
    r"modificaci[oó]n de cr[eé]dito|antifraude|padrones?|notificaci[oó]n|"
    r"licitaci[oó]n.*(?:barra|puesto|autorizaci[oó]n o licencia para instalar))",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXP = re.compile(r"(?i)\bexp:\s*([\d/]+-ur-[\w-]+)")
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _parse_fecha_iso(text: str) -> str | None:
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    for fn in (_parse_fecha_dmy, _parse_fecha_iso):
        d = fn(text)
        if d:
            return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _slug_to_title(url: str) -> str:
    slug = urllib.parse.unquote(url.rstrip("/").split("/")[-1])
    title = slug.replace("-", " ").strip()
    return title[:500] if title else url


def _normalize_key(text: str) -> str:
    t = unescape(text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _apply_portal_geometry(rec: dict[str, Any], geom: dict[str, Any], *, source_url: str) -> None:
    rec["geom_geojson"] = geom
    rec["geometry_crs"] = "EPSG:4326"
    rec["geometry_axis_order"] = "xy"
    rec["geometry_source"] = "portal_wfs"
    rec["geometry_source_url"] = source_url
    rec["coord_source"] = "portal_geometry_centroid"
    centroid = geometry_centroid(geom)
    if centroid:
        rec["lat"], rec["lon"] = centroid


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "modificaci" in b and "puntual" in b:
        return "modificación PGM"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "plan parcial" in b or re.search(r"sector s-", b):
        return "plan parcial"
    if "proyecto de urbaniz" in b or "unidad de ejecuci" in b:
        return "proyecto de urbanización"
    if "interpretaci" in b:
        return "interpretación PGM"
    if "informaci" in b and "públic" in b:
        return "información pública"
    if "pgm" in b or "plan general" in b:
        return "PGM"
    if "licencia" in b and "obra" in b:
        return "licencia publicada"
    return "urbanismo"


class CalahorraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress calahorra.es (documentos) + sede STA tablón/catálogo + UrbanCity WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_INSTRUMENTOS_URL)
        self._wfs_rows: list[dict[str, Any]] | None = None
        self._geom_index: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-calahorra/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.calahorra.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-calahorra/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if "licencias" not in path.name:
            rows = reviewed_records(path, rows)
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
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except json.JSONDecodeError:
                    pass
        return rows

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _collect_tablon_raw(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "TABLON"):
            title = str(item.get("descriptionProc") or "").strip()
            if not title or title in ("dESCRIPCION", "oRIGEN"):
                continue
            dboid = str(item.get("dboid") or title)
            rem = item.get("remitent") or {}
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "remitente": str(rem.get("description") or rem.get("code") or ""),
                    "origen": "tablon_sta",
                    "blob": title,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        """Páginas informativas (catálogo STA); no son concesiones publicadas."""
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            keywords = item.get("keywordList") or []
            kw_codes = {str(k.get("code") or "") for k in keywords}
            if not (kw_codes & {"UR", "URB", "URBANISMO"} or RE_LICENCIA.search(name)):
                continue
            if re.search(r"(?i)^modelo\s+\d|comunicaci[oó]n previa|declaraci[oó]n responsable", name):
                continue
            url = f"{CATALOGO_URL}#tramite={code}"
            rows.append(
                {
                    "id": _stable_id("lic", f"info:{code}"),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": MUNICIPIO,
                    "titulo": name[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                    "nota": "Trámite del catálogo sede; no concesión publicada",
                }
            )
        return rows[:5]

    def _collect_documento_urls(self) -> list[str]:
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls: list[str] = []
        for sm in DOCUMENTO_SITEMAPS:
            try:
                xml = self._fetch(f"{self.web_base}/{sm}")
                root = ET.fromstring(xml)
            except (urllib.error.URLError, ET.ParseError):
                continue
            for loc in root.findall(".//sm:loc", ns):
                if loc.text and RE_DOC_PATH.search(loc.text):
                    urls.append(loc.text.strip())
        return sorted(set(urls))

    def _documento_title(self, url: str) -> str:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return _slug_to_title(url)
        m = RE_TITLE.search(html)
        if not m:
            return _slug_to_title(url)
        title = _strip_html(m.group(1))
        title = re.sub(r"\s*-\s*Ayuntamiento de Calahorra\s*$", "", title, flags=re.I)
        return title[:500] or _slug_to_title(url)

    def _collect_documento_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._collect_documento_urls():
            titulo = self._documento_title(url)
            blob = f"{titulo} {url}"
            if not RE_PROYECTO.search(blob) and not RE_DOC_PATH.search(url):
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(blob),
                "tipo": _proyecto_tipo(blob),
                "url": url,
                "source": "ayuntamiento",
                "origen": "web_documento",
            }
            exp = RE_EXP.search(titulo)
            if exp:
                rec["expediente"] = exp.group(1)
            self._attach_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_rows is not None:
            return self._wfs_rows
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(self.wfs_url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_rows = rows
            return rows
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            name = str(props.get("name") or props.get("description") or "").strip()
            if not name:
                continue
            instr = str(props.get("instrument_type_name") or "")
            blob = f"{name} {instr}"
            fecha = _parse_fecha_iso(str(props.get("approval_date") or "")) or _parse_fecha_iso(
                str(props.get("publish_date") or "")
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{props.get('id')}:{name}"),
                "municipio": MUNICIPIO,
                "titulo": name[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(blob) if instr else str(props.get("instrument_type_group_name") or "instrumento"),
                "url": f"{self.web_base}/?codResi=1",
                "source": "ayuntamiento",
                "origen": "urbancity_wfs",
                "instrument_type": instr or None,
            }
            if isinstance(geom, dict) and geom.get("type"):
                _apply_portal_geometry(rec, geom, source_url=self.wfs_url)
            rows.append(rec)
        self._wfs_rows = rows
        return rows

    def _build_geom_index(self) -> dict[str, dict[str, Any]]:
        if self._geom_index is not None:
            return self._geom_index
        index: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wfs_proyectos():
            if not record_geometry(rec):
                continue
            key = _normalize_key(str(rec.get("titulo") or ""))
            if key and key not in index:
                index[key] = rec
            for token in key.split():
                if len(token) >= 6 and token not in index:
                    index[token] = rec
        self._geom_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = _normalize_key(str(rec.get("titulo") or ""))
        if not blob:
            return
        index = self._build_geom_index()
        hit = index.get(blob)
        if not hit:
            for token in blob.split():
                if len(token) >= 6 and token in index:
                    hit = index[token]
                    break
        if not hit:
            return
        for field in (
            "geom_geojson",
            "geometry_crs",
            "geometry_axis_order",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if hit.get(field) is not None:
                rec[field] = hit[field]

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
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
        if raw.get("origen") == "referencia_portal":
            return raw if raw.get("id") else None
        if RE_TABLON_SKIP.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if re.search(r"(?i)\bsolicitud\b", blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or TABLON_URL)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
            "titulo": titulo,
        }
        self._attach_geometry(rec)
        if rec.get("lat") is not None and rec.get("lon") is not None:
            rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources = (
            self._collect_wfs_proyectos()
            + self._collect_documento_proyectos()
            + [self._to_proyecto(r) for r in self._collect_tablon_raw()]
        )
        for rec in sources:
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        raw = self._collect_licencia_info_pages() + self._collect_tablon_raw()
        for item in raw:
            rec = self._to_licencia(item)
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
            "wfs": sum(1 for r in rows if r.get("origen") == "urbancity_wfs"),
            "documento": sum(1 for r in rows if r.get("origen") == "web_documento"),
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
