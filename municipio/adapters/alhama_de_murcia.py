from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://ayuntamiento.alhamademurcia.es"
DATOS_BASE = "https://datos.alhamademurcia.es"
SEDE_BASE = "https://alhamademurcia.sedelectronica.es"
SUBSEDE_TRIBUTARIA = "https://subsedeelectronicagestiontributaria.alhamademurcia.es"
MUNICIPIO = "Alhama de Murcia"
ID_PREFIX = "alhama-de-murcia"
COD_INE = "30003"

SEED_PAGES = (
    f"{WEB_BASE}/planeamientos-desarrollo.asp",
    f"{WEB_BASE}/areas/area.asp?id=1",
    f"{WEB_BASE}/documentos-tramitacion.asp",
    f"{WEB_BASE}/modificaciones-aprobadas-definitivamente.asp",
)
TABLON_URL = f"{WEB_BASE}/tablon.asp"

WFS_BASE = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Alhama%20de%20Murcia%27"
    "&outputFormat=application/json&srsName=EPSG:4326"
)

RE_LINK = re.compile(r'href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TABLON_AVISO = re.compile(
    r'href="((?:https://ayuntamiento\.alhamademurcia\.es)?/avisot\.asp\?id=\d+)"[^>]*itemprop="url"[^>]*>([^<]+)',
    re.I,
)
RE_TABLON_PDF = re.compile(
    r'href="(https?://(?:www\.)?datos\.alhamademurcia\.es/[^"]+\.pdf)"[^>]*(?:target="_blank")?[^>]*>([^<]+)',
    re.I,
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(proceso selectivo|convocatoria.*empleo|pr[aá]cticas extracurriculares|"
    r"subvenci[oó]n|feria de alhama|libro de la feria|calendario fiscal|ordenanzas fiscales|"
    r"registro de actividades de tratamiento|ayudas econ[oó]micas.*cel[ií]aca|"
    r"mercado semanal|venta ambulante|puesto.*plaza de abastos|colegio ricardo)",
)
RE_TITLE = re.compile(r"<title>\s*Ayuntamiento de Alhama de Murcia\s*-\s*(.+?)\s*</title>", re.I | re.S)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|obra)|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgmo|pgou|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|reparcel|estudio de detalle|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|suelo|unidad de actuaci[oó]n|"
    r"parcela|zona su|borm|edicto|ambiental estrat[eé]gico|documento digital|avance)",
)
RE_SKIP = re.compile(
    r"(?i)(aviso legal|pol[ií]tica de|cookies|browsehappy|facebook|twitter|instagram|"
    r"youtube|sugerencias|farmacias|telefonos|callejero|dependencias|mapa web|"
    r"semana santa|turismo|fiesta de los mayos|ingles|javascript:)",
)
RE_AMBITO = re.compile(
    r"(?i)\b(?:NUPP|NUI|SGC|SGEL|SGI|SUNS|SUN|SU|UA|PP|MOD|ZEP|CN|PER|API|UAR|UAT|UAI|UAU|"
    r"ZI\d+|ZR\d+|ZDT|ZDG)(?:[\s\-.][A-Z0-9]+(?:[\s\-.][A-Z0-9]+)*)?\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_ambito(raw: str) -> str:
    s = unescape(raw or "").strip().upper()
    s = re.split(r"[.,;]", s, maxsplit=1)[0].strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+$", "", s)
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
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "modificaci" in b and "pgmo" in b:
        return "modificación PGMO"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "unidad de actuaci" in b:
        return "unidad de actuación"
    if "licencia" in b:
        return "licencia publicada"
    if "pgmo" in b:
        return "PGMO"
    return "urbanismo"


class AlhamaDeMurciaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web ASP ayuntamiento.alhamademurcia.es + datos.alhamademurcia.es + WFS CARM (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wfs_base = str(self.config.get("wfs_url") or WFS_BASE).split("&count=")[0].split("&startIndex=")[0]
        self.seed_pages = tuple(self.config.get("seed_pages") or SEED_PAGES)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 6))
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alhama-de-murcia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href.strip())
        if href.startswith("http"):
            return href
        return urljoin(f"{base or self.web_base}/", href)

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

    def _page_title(self, html: str, fallback: str) -> str:
        m = RE_TITLE.search(html or "")
        if m:
            return _strip_html(m.group(1))[:500]
        return fallback[:500]

    def _collect_links_from_html(self, html: str, page_url: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, inner in RE_LINK.findall(html or ""):
            label = _strip_html(inner)
            if not label or len(label) < 4:
                continue
            if RE_SKIP.search(label) or RE_SKIP.search(href):
                continue
            url = self._abs_url(href, self.web_base if "datos.alhamademurcia" not in href else DATOS_BASE)
            blob = f"{label} {url}"
            if "datos.alhamademurcia" in url.lower():
                pass
            elif not RE_PROYECTO.search(blob) and not href.lower().endswith(".pdf"):
                if not href.lower().endswith(".asp"):
                    continue
            rows.append(
                {
                    "titulo": label[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": url,
                    "origen": origen,
                    "blob": blob,
                }
            )
        if RE_PROYECTO.search(html) or "pgmo" in html.lower():
            title = self._page_title(html, page_url.split("/")[-1])
            if title and not RE_SKIP.search(title):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(html),
                        "url": page_url,
                        "origen": origen,
                        "blob": f"{title} {_strip_html(html)[:800]}",
                    }
                )
        return rows

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        seen_pages: set[str] = set()
        child_asp: set[str] = set()
        rows: list[dict[str, Any]] = []

        for seed in self.seed_pages:
            if seed in seen_pages:
                continue
            seen_pages.add(seed)
            try:
                html = self._fetch(seed)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            rows.extend(self._collect_links_from_html(html, seed, "web_seed"))
            for href, inner in RE_LINK.findall(html):
                if not href.lower().endswith(".asp") or href.startswith("http"):
                    if href.startswith("http") and self.web_base not in href:
                        continue
                path = href.split("?")[0]
                if path.startswith("/"):
                    child = f"{self.web_base}{path}"
                elif path.endswith(".asp"):
                    child = f"{self.web_base}/{path.lstrip('/')}"
                else:
                    continue
                if RE_SKIP.search(_strip_html(inner)):
                    continue
                child_asp.add(child)

        for child in sorted(child_asp):
            if child in seen_pages:
                continue
            seen_pages.add(child)
            try:
                html = self._fetch(child)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            rows.extend(self._collect_links_from_html(html, child, "web_planeamiento"))

        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, self.max_tablon_pages + 1):
            url = self.tablon_url if page == 1 else f"{self.tablon_url}?pagina={page}"
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                break
            found = 0
            for href, title in RE_TABLON_AVISO.findall(html):
                titulo = _strip_html(title)
                if not titulo or RE_TABLON_SKIP.search(titulo):
                    continue
                doc_url = self._abs_url(href)
                blob = titulo
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": doc_url,
                        "origen": "tablon_web",
                        "blob": blob,
                    }
                )
                found += 1
            for href, title in RE_TABLON_PDF.findall(html):
                titulo = _strip_html(title)
                if not titulo or RE_TABLON_SKIP.search(titulo):
                    continue
                blob = f"{titulo} {href}"
                if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": unquote(href),
                        "origen": "tablon_pdf",
                        "blob": blob,
                    }
                )
                found += 1
            if found == 0 and page > 1:
                break
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
                ambito_raw = str(props.get("Ambito") or "")
                ambito = _normalize_ambito(ambito_raw)
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
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
                index[ambito] = rec
                for alt in _ambito_codes_from_text(ambito_raw):
                    index.setdefault(alt, rec)
            if len(features) < step:
                break
            start += step
        self._wfs_index = index
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
        if RE_SKIP.search(blob):
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
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.web_base)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob) or "1970-01-01",
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
            "titulo": titulo,
        }
        self._attach_geometry(rec)
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_web_seeds() + self._collect_tablon():
            rec = self._to_proyecto(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_tablon():
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon": len(rows)}

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
