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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geography_control import normalize_geometry
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import WFS_BASE, resolve_municipio_wfs
from municipio.http import PortalReadError, read_response

WP_BASE = "https://www.ayuntamiento-losmolinos.es"
SEDE_BASE = "https://sede.ayuntamiento-losmolinos.es/eAdmin"
TRANSP_BASE = "https://transparencia.ayuntamiento-losmolinos.es"
MUNICIPIO = "Los Molinos"
ID_PREFIX = "los-molinos"
SITCM_VISOR = "https://www.comunidad.madrid/medio-ambiente/sistema-informacion-territorial-visor-sit"
SOURCE_ERRORS = (urllib.error.URLError, TimeoutError, PortalReadError)

URBANISMO_URL = f"{WP_BASE}/?page_id=36668"

DEFAULT_TRANSPARENCIA_PAGES: list[dict[str, Any]] = [
    {"page_id": 185, "section": "planeamiento", "tipo": "planeamiento"},
]

DEFAULT_WP_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WP_BASE}/?p=40276",
    f"{WP_BASE}/?p=10954",
]

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLAN",
    "PGOU",
    "AVANCE",
    "UA-",
    "SAU-",
    "ESTUDIO",
    "CONVENIO",
    "REPARCEL",
    "APROBACION",
)

DEFAULT_TRAMITE_IDS = (34, 35, 36, 37, 51)

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)EXP\.?\s*([0-9]+/[0-9]{4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable.*obra|"
    r"comunicaci[oó]n previa|ordenanza.*licencia|primera ocupaci|obra mayor|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental|de detalle)|ua-\d|sau-|ue-\d|"
    r"avance|normas subsidiarias|memoria|planos|bocm)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|iae|cobranza|tribut|presupuest|empleo|igualdad|notificaci[oó]n telem)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UA|SAU|UE|AD|AN|AI|PAU|S)-[\w\d.\-]+)\b")
RE_MODAL_TITLE = re.compile(
    r'id="modalInformacion(\d+)"[^>]*>.*?<h4[^>]*>([^<]+)',
    re.I | re.S,
)
RE_ABRIR_CODE = re.compile(r"abrir\(['\"]([^'\"]+)['\"]\)")
RE_ABRIR_TITLE = re.compile(
    r"abrir\(['\"]([^'\"]+)['\"]\)[^>]*>([^<]+)</a>",
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://www\.ayuntamiento-losmolinos\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


def _doc_url(sede_base: str, code: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(code, safe='')}&tipo=doc&mode=ori"
    )


def _pdf_url(token: str, sede_base: str) -> str:
    return _doc_url(sede_base, token)


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "avance" in n and "pgou" in n:
        return "avance PGOU"
    if "plan parcial" in n or "plan especial" in n or "pgou" in n or re.search(r"ua-\d|sau-|ue-\d", n):
        return "planeamiento"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "memoria" in n:
        return "memoria"
    return default


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de los molinos", " finca "):
        if marker in low:
            low = low.split(marker, 1)[-1 if marker == " finca " else 0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 4]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and k not in {"molinos", "general", "avance", "bloque", "documento"}:
            seen.add(k)
            out.append(p)
    return out[:8]


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class LosMolinosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + sede eAdmin (tablón + trámites) + transparencia + SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.tramite_ids = [int(x) for x in (self.config.get("tramite_ids") or DEFAULT_TRAMITE_IDS)]
        self.transp_pages = list(
            self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES
        )
        self.wp_seed_pages = [str(u) for u in (self.config.get("wp_seed_pages") or DEFAULT_WP_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_municipio = str(
            geom_cfg.get("municipio_filter")
            or resolve_municipio_wfs(MUNICIPIO)
            or "LOS MOLINOS"
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._wfs_catalogue: list[dict[str, Any]] | None = None
        self._unreachable_hosts: dict[str | None, str] = {}
        self._unavailable_sources: dict[tuple[str, str], dict[str, str]] = {}

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-los-molinos/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        raw, headers = read_response(req, timeout=10, attempts=2)
        charset = headers.get_content_charset() or (
            "utf-8" if "ayuntamiento-losmolinos" in url else "iso-8859-1"
        )
        return raw.decode(charset, errors="replace")

    def _fetch_source(self, source: str, url: str, data: bytes | None = None) -> str:
        host = urllib.parse.urlsplit(url).hostname
        error = self._unreachable_hosts.get(host)
        if error is None:
            try:
                return self._fetch(url, data=data)
            except SOURCE_ERRORS as exc:
                error = str(exc)
                cause = exc.__cause__ or exc
                # urllib wraps connection failures in URLError. An HTTP response or a
                # broken body only establishes failure of the requested resource.
                if isinstance(cause, urllib.error.URLError) and not isinstance(cause, urllib.error.HTTPError):
                    self._unreachable_hosts[host] = error
        self._unavailable_sources.setdefault((source, url), {"source": source, "url": url, "error": error})
        return ""

    def _begin_collection(self) -> None:
        self._unreachable_hosts.clear()
        self._unavailable_sources.clear()
        self._wfs_cache = None
        self._wfs_catalogue = None

    def _coverage(self) -> dict[str, Any]:
        if not self._unavailable_sources:
            return {"status": "ok"}
        unavailable = list(self._unavailable_sources.values())
        sources = dict.fromkeys(item["source"] for item in unavailable)
        return {
            "status": "partial",
            "reason": f"los_molinos_sources_unavailable: {', '.join(sources)}",
            "unavailable_sources": unavailable,
        }

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href).replace("&amp;", "&"))

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            fecha_fin = _parse_fecha_dmy(period_m.group(2)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "fecha_fin": fecha_fin,
                "url": detail_url,
                "doc_token": doc_token,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url(doc_token, self.sede_base)
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        html = self._fetch_source("tablon", f"{self.sede_base}/Tablon.do?action=verAnuncios", data=body)
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        html = self._fetch_source("tablon", f"{self.sede_base}/Tablon.do?action=verAnuncios")
        by_id = self._parse_tablon_html(html)
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _extract_transparencia_docs(self, html: str) -> list[tuple[str, str]]:
        by_code: dict[str, str] = {}
        for code, anchor_title in RE_ABRIR_TITLE.findall(html):
            title = _clean_title(anchor_title)
            if title and title.lower() != "ver documento":
                by_code[code] = title
        for m in re.finditer(r"<h[234][^>]*>([^<]+)</h[234]>", html, re.I):
            section = _clean_title(m.group(1))
            if section:
                for code in RE_ABRIR_CODE.findall(m.group(0)):
                    by_code.setdefault(code, section)
        return [(title, code) for code, title in by_code.items()]

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self.transp_pages:
            page_id = int(page["page_id"])
            section = str(page.get("section") or page_id)
            default_tipo = str(page.get("tipo") or "urbanismo")
            page_url = f"{self.transp_base}/?page_id={page_id}"
            html = self._fetch_source("transparencia_planeamiento", page_url)
            for title, code in self._extract_transparencia_docs(html):
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", code),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(title),
                    "tipo": _proyecto_tipo(title, default_tipo),
                    "url": page_url,
                    "pdf_url": _doc_url(self.sede_base, code),
                    "source": "ayuntamiento",
                    "origen": section,
                    "doc_code": code,
                }
                self._enrich_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_wp_docs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.wp_seed_pages:
            html = self._fetch_source("web_urbanismo", page_url)
            for m in RE_WP_PDF.finditer(html):
                href = m.group(1)
                pdf_url = self._abs_wp(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ").replace("_", " ")
                titulo = name[:500]
                blob = f"{titulo} {pdf_url}"
                if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    licencias.append(
                        {
                            "id": _stable_id("lic", pdf_url),
                            "fecha_concesion": _parse_fecha_dmy(pdf_url),
                            "tipo": titulo[:120],
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": titulo,
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "source": "ayuntamiento",
                            "origen": "urbanismo_wp",
                            "nota": "Modelo/formulario informativo; no concesión publicada",
                        }
                    )
                elif RE_PROYECTO.search(blob) and not RE_EXCLUDE.search(blob):
                    rec: dict[str, Any] = {
                        "id": _stable_id("proy", pdf_url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha_dmy(pdf_url),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": "urbanismo_wp",
                    }
                    self._enrich_geometry(rec)
                    proyectos.append(rec)
        return proyectos, licencias

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        url = f"{self.sede_base}/Registrar.do?action=listadoEntradas"
        html = self._fetch_source("catalogo_tramites", url)
        titles: dict[str, str] = {}
        for m in RE_MODAL_TITLE.finditer(html):
            tid, title = m.group(1), _clean_title(m.group(2))
            if tid in {str(x) for x in self.tramite_ids}:
                titles[tid] = title
        rows: list[dict[str, Any]] = []
        for tid in self.tramite_ids:
            title = titles.get(str(tid))
            if not title:
                continue
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tid}"
            rows.append(
                {
                    "id": _stable_id("lic", f"tramite-{tid}"),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede; no concesión publicada",
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _wfs_query_url(self, cql: str, count: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "sitcm:VPLA_V_AMBITO",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        return f"{self.wfs_url}?{params}"

    def _wfs_query(self, cql: str, count: int = 20) -> tuple[list[dict[str, Any]], bool]:
        url = self._wfs_query_url(cql, count)
        body = self._fetch_source("sitcm_ambitos", url)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return [], False
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            return [], False
        raw_features = data.get("features")
        if not isinstance(raw_features, list):
            return [], False
        features = [f for f in raw_features if isinstance(f, dict)]
        matched = data.get("numberMatched")
        return features, type(matched) is int and len(features) == len(raw_features) == matched

    def _wfs_municipio_filter(self) -> str:
        return "DS_MUNICIPIO='" + self.wfs_municipio.replace("'", "''") + "'"

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        feats, complete = self._wfs_query(self._wfs_municipio_filter(), count=120)
        if complete:
            self._wfs_catalogue = feats
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _collect_sitcm_ambitos(self) -> list[dict[str, Any]]:
        self._load_wfs_ambitos()
        if not self._wfs_catalogue:
            raise ValueError("Los Molinos requires a complete, nonempty SITCM catalogue when municipal planning is unavailable")
        source_url = self._wfs_query_url(self._wfs_municipio_filter(), 120)
        rows = []
        seen: set[str] = set()
        for feature in self._wfs_catalogue:
            props = feature.get("properties") or {}
            code = props.get("CD_UNI")
            title = str(props.get("DS_NOMB_AMB") or "").strip()
            registry = str(props.get("CD_REUR") or "").strip()
            if (props.get("DS_MUNICIPIO") != self.wfs_municipio or not isinstance(code, str)
                    or not code.strip() or code in seen or not title or not registry.isdecimal()):
                raise ValueError(f"Invalid Los Molinos SITCM sector identity: {code}")
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                raise ValueError(f"Missing Los Molinos SITCM polygon for {code}")
            geometry = normalize_geometry(geometry, "EPSG:4326")
            center = geometry_centroid(geometry)
            if center is None:
                raise ValueError(f"Invalid Los Molinos SITCM polygon for {code}")
            seen.add(code)
            rows.append({
                "id": _stable_id("proy", f"sitcm:{code}"),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": props.get("FC_BOCM"),
                "tipo": "planeamiento",
                "url": SITCM_VISOR,
                "source": "sitcm",
                "catalog_source": "sitcm",
                "bocm_source_id": "sitcm",
                "origen": "sitcm_ambitos",
                "exp_numero_original": f"REUR {registry} / {code}",
                "sitcm_code": code,
                "ambito_sit": title,
                "geom_geojson": geometry,
                "geometry_crs": "EPSG:4326",
                "geometry_source": "portal_wfs",
                "geometry_source_url": source_url,
                "coord_source": "portal_geometry_centroid",
                "lat": center[0],
                "lon": center[1],
            })
        return rows

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper()
            feat = cache.get(code)
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            if self._wfs_catalogue is not None and "\\" not in pattern:
                expression = "".join(
                    ".*" if char == "%" else "." if char == "_" else re.escape(char)
                    for char in pattern.replace("''", "'")
                )
                matches = re.compile(expression, re.IGNORECASE | re.DOTALL)
                feats = [f for f in self._wfs_catalogue
                         if matches.fullmatch(str((f.get("properties") or {}).get("DS_NOMB_AMB") or ""))][:10]
            else:
                feats, _ = self._wfs_query(
                    f"{self._wfs_municipio_filter()} AND DS_NOMB_AMB ILIKE '{pattern}'",
                    count=10,
                )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        merged = _merge_geometries(same_name or [candidates[0][2]])
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39)*2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}",
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|ordenanza.*licencia)", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _title_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_EXCLUDE.search(title):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        self._enrich_geometry(out)
        return out

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

    def _collect_licencias(self, *, replace_duplicates: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self._begin_collection()
        tablon = self._collect_tablon()
        rows: dict[str, dict[str, Any]] = {}

        def add(row: dict[str, Any] | None) -> None:
            if row and (replace_duplicates or row["id"] not in rows):
                rows[row["id"]] = row

        for rec in tablon.values():
            add(self._title_to_licencia(rec))
        _, wp_lic = self._collect_wp_docs()
        for rec in wp_lic:
            add(rec)
        for rec in self._collect_tramites_urbanismo():
            add(rec)
        return list(rows.values()), {
            **self._coverage(),
            "tablon_items": len(tablon),
            "tramites": len(self.tramite_ids),
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias()
        return self._save_collection(out_jsonl, rows, coverage)

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias(replace_duplicates=True)
        return self._save_collection(out_jsonl, rows, coverage, state_path, retain_existing=True)

    def _collect_proyectos(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self._begin_collection()
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        wp_proy, _ = self._collect_wp_docs()
        for rec in wp_proy:
            add(rec)
        for rec in self._collect_transparencia_proyectos():
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))
        if self._unavailable_sources and not rows:
            for row in self._collect_sitcm_ambitos():
                add(row)

        return rows, {
            **self._coverage(),
            "wp_docs": len(wp_proy),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon"),
            "sitcm_ambitos": sum(1 for r in rows if r.get("origen") == "sitcm_ambitos"),
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        return self._save_collection(out_jsonl, rows, coverage)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        return self._save_collection(out_jsonl, rows, coverage, state_path)

    def _save_collection(
        self, out_jsonl: Path, rows: list[dict[str, Any]], coverage: dict[str, Any],
        state_path: Path | None = None, *, retain_existing: bool = False,
    ) -> dict[str, Any]:
        partial = coverage["status"] == "partial"
        existing = self._load_jsonl(out_jsonl) if state_path is not None or partial else []
        if partial or retain_existing:
            by_id = {row["id"]: row for row in existing}
            for row in rows:
                if partial and row["id"] in by_id:
                    by_id[row["id"]].update({key: value for key, value in row.items() if value is not None})
                else:
                    by_id[row["id"]] = row
            rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        result = {"rows": len(rows), **coverage}
        if state_path is not None:
            result["added"] = max(0, len(rows) - len(existing))
            state_path.write_text(
                json.dumps(
                    {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), **result},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return result
