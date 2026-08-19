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

PORTAL_BASE = "http://elvellon.es"
SEDE_BASE = "https://sedeelvellon.eadministracion.es"
MUNICIPIO = "El Vellón"
ID_PREFIX = "el-vellon"

TRAMITES_URL = f"{PORTAL_BASE}/Ciudadanos/Tr%C3%A1mites-Personales"
NOTICIAS_URL = f"{PORTAL_BASE}/Ayuntamiento/Noticias"
PLENO_URL = f"{PORTAL_BASE}/Ayuntamiento/Pleno"
ORDENANZAS_URL = f"{PORTAL_BASE}/Ayuntamiento/Normativa-Municipal/Ordenanzas"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
PGOU_CM_URL = (
    "https://www.comunidad.madrid/transparencia/sites/default/files/"
    "regulation/documents/documento_inicial_estrategico_5.pdf"
)

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "EL VELLÓN"

DEFAULT_SEED_PAGES: list[str] = [
    TRAMITES_URL,
    NOTICIAS_URL,
    PLENO_URL,
    ORDENANZAS_URL,
]

DEFAULT_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "path": "/Portals/4/documentos/Licencia de Obras Mayores.pdf?ver=2023-01-27-092709-660",
        "tipo": "licencia obras mayores",
        "titulo": "Licencia de obras mayores (modelo)",
    },
    {
        "path": "/Portals/4/documentos/Licencia Obras.pdf?ver=2023-01-27-092710-127",
        "tipo": "licencia obras menores",
        "titulo": "Licencia de obras menores (modelo)",
    },
    {
        "path": "/Portals/4/documentos/Primera Ocupacion.pdf?ver=2023-01-27-093723-870",
        "tipo": "licencia primera ocupación",
        "titulo": "Licencia de primera ocupación (modelo)",
    },
    {
        "path": "/Portals/4/documentos/Licencia de Actividad.pdf?ver=2023-01-27-092709-597",
        "tipo": "licencia urbanística actividad",
        "titulo": "Licencia urbanística de actividad (modelo)",
    },
    {
        "path": "/Portals/4/documentos/Acto Comunicado.pdf?ver=2023-01-27-092710-160",
        "tipo": "acto comunicado",
        "titulo": "Acto comunicado (licencia)",
    },
    {
        "path": "/Portals/4/documentos/Actividad o Funcionamiento.pdf?ver=2023-01-27-095404-457",
        "tipo": "licencia actividad-funcionamiento",
        "titulo": "Licencia de actividad o funcionamiento (modelo)",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|cedula urban|c[eé]dula urban|acto comunicado|"
    r"actividad.*funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|parcela|bando|unidad(?:es)? de ejecuci[oó]n|reserva urbana|"
    r"\bP-\d+\b|consultorio|licitaci[oó]n.*obra|obra.*consultorio|"
    r"edicto.*urban|bocm|estudio (?:de )?detalle|"
    r"infraestructura|ambiental|urbanizaci[oó]n|convenio urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"activaci[oó]n profesional|catel|pafel|uaef|bibliob[uú]s|campamento|"
    r"igualdad|bolsa|perros|vacunaci[oó]n|impuesto|tributo|ibi|basura|pastos|"
    r"acta pleno|acta de pleno|acta de constituci[oó]n|pr[eé]stamos|arqueo|"
    r"retribuciones|delegaciones|concurso de carteles|fiestas|tanatorio|"
    r"ordenanza recogida veh[ií]culos)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b(P-\d+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM[- ]?(\d{4})[- ]?(\d{2})[- ]?(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PORTAL_PDF = re.compile(
    r'href="((?:https?://(?:www\.)?elvellon\.es)?/Portals/4/[^"]+\.(?:pdf|PDF)[^"]*)"',
    re.I,
)
RE_PORTAL_PDF_LINK = re.compile(
    r'<a[^>]+href="((?:https?://(?:www\.)?elvellon\.es)?/Portals/4/[^"]+\.(?:pdf|PDF)[^"]*)"[^>]*>'
    r"([^<]*)</a>",
    re.I,
)


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
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = re.search(r"ver=(\d{4})-(\d{2})-(\d{2})", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(urllib.parse.unquote(url)).name)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bp-\d", n) or "reserva urbana" in n:
        return "reserva urbana"
    if "consultorio" in n or "licitaci" in n:
        return "obra pública"
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "bocm" in n:
        return "publicación BOCM"
    if "nnss" in n or "normas subsidiarias" in n or "normas urban" in n:
        return "normas subsidiarias"
    if "planeamiento" in n or "pgou" in n:
        return "planeamiento"
    if "aprobaci" in n:
        return "aprobación"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de el ", " licitaci"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 2]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


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


class ElVellonAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal DNN (elvellon.es) + sede eAdmin + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.portal_base = str(self.config.get("portal_base") or PORTAL_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-vellon/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.portal_base}/", unescape(href).replace("&amp;", "&"))

    def _extract_pdfs(self, html: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for m in RE_PORTAL_PDF_LINK.finditer(html):
            url = self._abs_url(unescape(m.group(1).replace("&amp;", "&")))
            if url in seen:
                continue
            seen.add(url)
            label = unescape(m.group(2).strip())
            if not label or label.lower().endswith(".pdf"):
                label = unescape(urllib.parse.unquote(Path(url).name))
            name = re.sub(r"\.pdf$", "", label, flags=re.I).replace("-", " ").replace("_", " ")
            out.append((name[:500], url))
        for m in RE_PORTAL_PDF.finditer(html):
            url = self._abs_url(unescape(m.group(1).replace("&amp;", "&")))
            if url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
            out.append((name[:500], url))
        return out

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites licencias y autorizaciones",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias y autorizaciones — trámites personales",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF de licencias urbanísticas y actividad",
                "origen": "portal_tramites",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación telemática de trámites",
                "url": f"{self.sede_base}/PortalCiudadano/",
                "source": "ayuntamiento",
                "nota": "Maggioli eAdmin (sedeelvellon.eadministracion.es)",
                "origen": "sede",
            },
        ]

    def _collect_licencia_forms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_pdfs") or DEFAULT_LICENCIA_PDFS:
            pdf_url = self._abs_url(str(item["path"]))
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_pdf_url(pdf_url),
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": self.tramites_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Modelo descargable; no concesión publicada",
                    "origen": "formularios_portal",
                }
            )
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            return rows
        seen = {r["pdf_url"] for r in rows if r.get("pdf_url")}
        for title, pdf_url in self._extract_pdfs(html):
            blob = f"{title} {pdf_url}"
            if pdf_url in seen:
                continue
            if RE_EXCLUDE.search(blob):
                continue
            if not RE_LICENCIA.search(blob):
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_pdf_url(pdf_url),
                    "tipo": title[:120] or "formulario urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": f"Formulario: {title}"[:500],
                    "url": self.tramites_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Modelo descargable; no concesión publicada",
                    "origen": "tramites_portal",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
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
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
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
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
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

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_pgou_seed(self) -> list[dict[str, Any]]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", "pgou-avance"),
            "municipio": MUNICIPIO,
            "titulo": "Avance de Planeamiento — Plan General de Ordenación Urbana de El Vellón",
            "fecha": "2022-02-21",
            "tipo": "planeamiento",
            "url": PGOU_CM_URL,
            "pdf_url": PGOU_CM_URL,
            "source": "ayuntamiento",
            "origen": "pgou_cm",
            "nota": "Documento Inicial Estratégico PGOU (contrato redacción 2022, OMICRON AMEPRO)",
        }
        return [rec]

    def _pdf_to_proyecto(self, title: str, pdf_url: str, page_url: str) -> dict[str, Any] | None:
        blob = f"{title} {pdf_url}"
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _fecha_from_pdf_url(pdf_url) or _parse_fecha_dmy(title),
            "tipo": _proyecto_tipo(blob),
            "url": page_url,
            "pdf_url": pdf_url,
            "source": "ayuntamiento",
            "origen": "portal_pdf",
        }
        self._enrich_geometry(rec)
        return rec

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, pdf_url in self._extract_pdfs(html):
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                rec = self._pdf_to_proyecto(title, pdf_url, page_url)
                if rec:
                    rows.append(rec)
        return rows

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_licencia_forms():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for rec in self._collect_licencia_forms():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_pgou_seed():
            add(rec)
        for rec in self._collect_seed_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        sit_n = sum(1 for r in rows if r.get("origen") == "sit_wfs")
        pdf_n = sum(1 for r in rows if r.get("origen") == "portal_pdf")
        geom_n = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sit_n,
            "portal_pdfs": pdf_n,
            "with_geometry": geom_n,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
