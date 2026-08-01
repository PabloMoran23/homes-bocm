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
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WEB_BASE = "https://www.villadelprado.es"
TRANSPARENCIA_BASE = "http://transparencia.villadelprado.org"
URBANISMO_URL = f"{TRANSPARENCIA_BASE}/index.php/urbanismo"
SEDE_BASE = "https://sede.villadelprado.es"
TABLON_URL = f"{SEDE_BASE}/eAdmin/Tablon.do?action=inicioTablon"
MUNICIPIO = "Villa del Prado"
ID_PREFIX = "villa-del-prado"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLA DEL PRADO"

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WEB_BASE}/tu-ayuntamiento/impresos-y-solicitudes/577-licencia-obra-mayor",
    f"{WEB_BASE}/tu-ayuntamiento/impresos-y-solicitudes/162-obra-menor",
    f"{WEB_BASE}/tu-ayuntamiento/impresos-y-solicitudes/900-cartel-identificativo-obras-online",
]

AMBITO_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("sector 02", "S-02 LA FLORIDA"),
    ("la florida", "S-02 LA FLORIDA"),
    ("las hoyas", "UE-10"),
    ("el cristo", "S-01 EL CRISTO"),
    ("los palomares", "S-03 LOS PALOMARES"),
    ("san francisco de meredo", "S-04 SAN FRANCISCO DE MEREDO"),
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|obra)|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|cartel.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|ponp|nnss|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"memoria|planos|bocm|edicto|aprobaci[oó]n|parcela|suelo|sector|"
    r"las hoyas|la florida|catalogo|normas urban|ordenaci[oó]n|acuerdo|"
    r"estudio (?:ambiental|de tr[aá]fico|hidrol|ruido|viabilidad))",
)
RE_SKIP = re.compile(
    r"(?i)(aviso legal|politica de privacidad|politica de cookies|registro de actividades|"
    r"volver arriba|de acuerdo|m[aá]s informaci[oó]n|facebook|twitter|instagram|"
    r"^inicio$|^indice$|^cap[ií]tulo|^hojas p|^planos$|^bocm$)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM = re.compile(r"BOCM[-_]?(\d{4})(\d{2})(\d{2})", re.I)
RE_BOCM_DASH = re.compile(r"bocm-(\d{4})(\d{2})(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_SECTION = re.compile(r"<p[^>]*>([^<]{8,200})</p>", re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


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
    for pat in (RE_BOCM, RE_BOCM_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n or "ponp" in n:
        return "plan especial"
    if "parcelaci" in n or "las hoyas" in n:
        return "proyecto de parcelación"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "ordenaci" in n or "clasificaci" in n:
        return "PGOU"
    if "bocm" in n:
        return "publicación BOCM"
    if "memoria" in n:
        return "memoria planeamiento"
    if "planos" in n or "plano" in n:
        return "planos"
    if "estudio" in n:
        return "estudio técnico"
    if "acuerdo" in n:
        return "acuerdo planeamiento"
    if "catalogo" in n or "catálogo" in n:
        return "catálogo PGOU"
    return "planeamiento"


class VillaDelPradoAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla corporativa + transparencia urbanismo + WFS SITCM (sede eAdmin inaccesible)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.licencia_pages = [
            str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villa-del-prado/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        href = unescape(href).replace("&amp;", "&").strip()
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{(base or self.transparencia_base)}/", href)

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._sitcm_cache is not None:
            return self._sitcm_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{self.wfs_municipio}'",
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache = {}
            return self._sitcm_cache
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        cache = self._load_sitcm_ambitos()
        feat = cache.get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{ambit_name.replace(chr(39), chr(39) * 2)}'"
        )
        query_url = (
            f"{self.wfs_url}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typeName={self.wfs_type}&outputFormat=application/json&srsName=EPSG:4326"
            f"&CQL_FILTER={urllib.parse.quote(cql)}"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        title_low = (title or "").lower()
        for keyword, ambit in AMBITO_KEYWORDS:
            if keyword in title_low:
                hit = self._geometry_from_ambit(ambit)
                if hit:
                    return hit
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _current_section(self, html: str, pos: int) -> str:
        chunk = html[:pos]
        sections = list(RE_SECTION.finditer(chunk))
        if sections:
            return _strip_html(sections[-1].group(1))
        h1 = RE_H1.search(chunk)
        if h1:
            return _strip_html(h1.group(1))
        return ""

    def _collect_urbanismo_links(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LINK.finditer(html):
            href = m.group(1)
            text = _strip_html(m.group(2))
            if not text or len(text) < 3:
                continue
            if RE_SKIP.search(text):
                continue
            url = self._abs_url(href)
            key = f"{text}|{url}"
            if key in seen:
                continue
            seen.add(key)
            section = self._current_section(html, m.start())
            blob = f"{section} {text} {url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                if "madrid.org/cartografia/planea" not in url and "/TRANSPARENCIA/URBANISMO" not in url:
                    continue
            rows.append(
                {
                    "titulo": text[:500],
                    "section": section[:300] if section else None,
                    "fecha": _parse_fecha_dmy(blob),
                    "url": url,
                    "blob": blob,
                    "origen": "transparencia_urbanismo",
                }
            )
        return rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = RE_H1.search(html)
            titulo = _strip_html(title_m.group(1)) if title_m else page_url
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia urbanística",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario/información de trámite; sin concesiones publicadas",
                    "origen": "impresos_web",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "urbanismo y planeamiento",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Documentación de planeamiento y proyectos",
                "origen": "transparencia_urbanismo",
            },
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — sede electrónica",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sede inaccesible (connection reset) en el momento de la ingesta",
                "origen": "tablon_sede",
            },
        ]

    def _link_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        titulo = row["titulo"]
        if row.get("section") and row["section"] not in titulo:
            titulo = f"{row['section']} — {titulo}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("url") or titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": row.get("url") or self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _build_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in self._collect_urbanismo_links():
            rec = self._link_to_proyecto(row)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _build_licencias(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_licencia_info_pages() + self._collect_licencia_pages():
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_licencias()
        n = self._write_jsonl(out_jsonl, rows)
        return {
            "ok": True,
            "rows": n,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_proyectos()
        n = self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "ok": True,
            "rows": n,
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
