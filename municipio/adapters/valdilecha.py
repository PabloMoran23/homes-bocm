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

WEB_BASE = "https://www.valdilecha.org"
SEDE_BASE = "https://valdilecha.eadministracion.es"
MUNICIPIO = "Valdilecha"
ID_PREFIX = "valdilecha"

URBANISMO_URL = f"{WEB_BASE}/urbanismo"
BANDOS_URL = f"{WEB_BASE}/pleno-municipal/bandos-y-anuncios"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VALDILECHA"

DEFAULT_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "path": "/Ficheros/Documentos/instanciagral.pdf",
        "tipo": "instancia general urbanismo",
        "titulo": "Instancia general (urbanismo)",
    },
    {
        "path": "/Ficheros/Documentos/DECLARACIONRESPONSABLEURBANISTICA2(1).pdf",
        "tipo": "declaración responsable urbanística",
        "titulo": "Declaración responsable urbanística",
    },
    {
        "path": "/Ficheros/Documentos/MODELODEAUTORIZACIONeditable(2).pdf",
        "tipo": "autorización urbanística",
        "titulo": "Modelo de autorización urbanística",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|farmacia|paintball)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|regimen.*licencia|"
    r"ordenanza.*licencia|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"estudio de detalle|modificaci[oó]n puntual|sector|sus[\s-]?r|aa[\s-]?\d|apd[\s-]?i|"
    r"contribuciones especiales|pfot|solar|impacto ambiental|entidad de conservaci[oó]n|"
    r"junta de compensaci[oó]n|sui[\s-]?\d|memoria|ordenaci[oó]n|calificaci[oó]n)",
)
RE_SKIP = re.compile(
    r"(?i)(presupuesto|modificaci[oó]n presupuestaria|cuenta general|calendario fiscal|"
    r"ordenanza (?:de )?(?:tasa|fiscal|basura|cementerio|deporte|animales|icic)|"
    r"regimen de dedicaci[oó]n|nombramiento|candidatura|juez de paz|carnaval|reinas|"
    r"acad[eé]micos|subvenci[oó]n|bando barra|impuesto|tributo|padron|padr[oó]n|"
    r"estatutos mise|comunidad de regantes|convocatoria comercio)",
)
RE_PDF_LINK = re.compile(
    r'<a\s+href="([^"]+\.pdf[^"]*)"[^>]*?(?:tittle|title)="([^"]*)"[^>]*>([^<]*)</a>'
    r'|<a\s+href="([^"]+\.pdf[^"]*)"[^>]*>([^<]*)</a>',
    re.I,
)
RE_BOLD_SECTION = re.compile(
    r'<(?:span|strong)[^>]*style="[^"]*font-weight:\s*(?:bold|700)[^"]*"[^>]*>([^<]+)</(?:span|strong)>'
    r'|<h[1-6][^>]*>([^<]+)</h[1-6]>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBIT_CODE = re.compile(
    r"(?i)\b(AA[\s\-]?\d+|SUS[\s\-]?(?:R|AE)[\s\-]?\d+|APD[\s\-]?I\d+|SUSR\s*\d+)\b"
)


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


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _abs_url(href: str, base: str = WEB_BASE) -> str:
    return urllib.parse.urljoin(f"{base}/", unescape(href).replace("&amp;", "&"))


def _normalize_ambit_code(raw: str) -> str:
    t = raw.upper().replace(" ", "").replace("_", "-")
    t = re.sub(r"SUSR(\d+)", r"SUS-R-\1", t)
    t = re.sub(r"SUS-R(\d+)", r"SUS-R\1", t)
    t = re.sub(r"SUS-R-(\d+)", lambda m: f"SUS-R-{m.group(1)}", t)
    t = re.sub(r"AA-?(\d+)", lambda m: f"AA-{m.group(1)}", t)
    t = re.sub(r"APD-?I(\d+)", lambda m: f"APD-I{m.group(1)}", t)
    t = re.sub(r"SUS-AE(\d+)", lambda m: f"SUS-AE{m.group(1)}", t)
    return t


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "convenio" in n:
        return "convenio urbanístico"
    if "memoria" in n:
        return "memoria PGOU"
    if "ordenacion" in n or "ordenación" in n:
        return "ordenación PGOU"
    if "ficha" in n:
        return "ficha gestión urbanística"
    if "capitulo" in n or "capítulo" in n or name.lower().startswith("c"):
        return "normativa PGOU"
    return "documento PGOU"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "pgou" in n or re.search(r"sus[\s-]?r|aa[\s-]?\d", n):
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "impacto ambiental" in n or "pfot" in n or "solar" in n:
        return "evaluación ambiental"
    return "urbanismo"


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


class ValdilechaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Neosoft (PGOU + bandos) + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.bandos_url = str(self.config.get("bandos_url") or BANDOS_URL)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._ambit_names: list[str] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdilecha/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdilecha/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _section_at(self, html: str, pos: int) -> str:
        chunk = html[max(0, pos - 4000) : pos]
        sections = [_clean_title(m.group(1) or m.group(2) or "") for m in RE_BOLD_SECTION.finditer(chunk)]
        sections = [s for s in sections if s and len(s) >= 5]
        return sections[-1] if sections else ""

    def _parse_pdf_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_LINK.finditer(html):
            href = m.group(1) or m.group(4) or ""
            tittle = _clean_title(m.group(2) or "")
            anchor = _clean_title(m.group(3) or m.group(5) or "")
            pdf_url = _abs_url(href)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            section = self._section_at(html, m.start())
            title = section or tittle or anchor or Path(pdf_url).stem
            if section and anchor and anchor.lower() not in section.lower():
                if len(anchor) > 4 and not anchor.lower().startswith("anuncio"):
                    title = f"{section}: {anchor}"
                else:
                    title = section
            elif tittle and len(tittle) > 4:
                title = tittle
            rows.append(
                {
                    "titulo": title[:500],
                    "pdf_url": pdf_url,
                    "url": page_url,
                    "fecha": _parse_fecha_dmy(f"{title} {pdf_url}"),
                    "blob": f"{title} {pdf_url}",
                }
            )
        return rows

    def _collect_pgou(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for rec in self._parse_pdf_links(html, self.urbanismo_url):
            name = Path(rec["pdf_url"]).name
            if RE_SKIP.search(name) and not RE_PROYECTO.search(name):
                continue
            row = {
                "id": _stable_id("proy", rec["pdf_url"]),
                "municipio": MUNICIPIO,
                "titulo": f"PGOU Valdilecha: {name}"[:500],
                "fecha": rec.get("fecha"),
                "tipo": _pgou_tipo(name),
                "url": self.urbanismo_url,
                "pdf_url": rec["pdf_url"],
                "source": "ayuntamiento",
                "origen": "pgou_urbanismo",
            }
            self._attach_geometry(row)
            rows.append(row)
        return rows

    def _collect_bandos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.bandos_url)
        except urllib.error.URLError:
            return []
        return self._parse_pdf_links(html, self.bandos_url)

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_pdfs") or DEFAULT_LICENCIA_PDFS:
            pdf_url = _abs_url(str(item["path"]))
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": self.urbanismo_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario/trámite informativo; no concesión publicada",
                    "origen": "urbanismo_formularios",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", SEDE_BASE),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": SEDE_BASE,
                "source": "ayuntamiento",
                "nota": "Trámites vía eAdmin; sin listado público de concesiones",
                "origen": "sede_eadmin",
            }
        )
        return rows

    def _load_ambitos(self) -> tuple[list[dict[str, Any]], list[str]]:
        if self._wfs_cache is not None and self._ambit_names is not None:
            return self._wfs_cache, self._ambit_names
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": f"DS_MUNICIPIO='{WFS_MUNICIPIO}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_cache = []
            self._ambit_names = []
            return self._wfs_cache, self._ambit_names
        feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
        self._wfs_cache = feats
        self._ambit_names = sorted(
            {str(f.get("properties", {}).get("DS_NOMB_AMB") or "") for f in feats if f.get("properties")}
        )
        return self._wfs_cache, self._ambit_names

    def _match_ambit_name(self, title: str, names: list[str]) -> str | None:
        codes = [_normalize_ambit_code(m.group(1)) for m in RE_AMBIT_CODE.finditer(title)]
        norm_names = {_normalize_ambit_code(n): n for n in names}
        for code in codes:
            for norm, orig in norm_names.items():
                if code == norm or code.replace("-", "") == norm.replace("-", ""):
                    return orig
        t = title.lower()
        best: str | None = None
        best_score = 0
        for name in names:
            nf = name.lower().replace(" ", "")
            score = 0
            for code in codes:
                cl = code.lower().replace(" ", "")
                if cl in nf or nf in cl:
                    score += 15
            if name.lower() in t:
                score += 12
            if score > best_score:
                best_score = score
                best = name
        return best if best_score >= 12 else None

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        feats, names = self._load_ambitos()
        if not feats or not names:
            return None
        ambit = self._match_ambit_name(title, names)
        if not ambit:
            return None
        chosen = [f for f in feats if str(f.get("properties", {}).get("DS_NOMB_AMB")) == ambit]
        merged = _merge_geometries(chosen)
        if not merged:
            return None
        esc = ambit.replace("'", "''")
        cql = f"DS_MUNICIPIO='{WFS_MUNICIPIO}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "20",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{WFS_BASE}?{params}",
            "coord_source": "portal_geometry_centroid",
            "geometry_ambit": ambit,
        }

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _bandos_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec.get("titulo") or ""
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        title = rec["titulo"]
        row: dict[str, Any] = {
            "id": _stable_id("proy", rec["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha"),
            "tipo": _proyecto_tipo(title),
            "url": rec.get("url") or self.bandos_url,
            "pdf_url": rec["pdf_url"],
            "source": "ayuntamiento",
            "origen": "bandos_anuncios",
        }
        self._attach_geometry(row)
        return row

    def _bandos_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(r"(?i)licencia|autorizaci[oó]n", blob):
            return None
        title = rec["titulo"]
        return {
            "id": _stable_id("lic", rec["pdf_url"]),
            "fecha_concesion": rec.get("fecha"),
            "tipo": "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": rec.get("url") or self.bandos_url,
            "pdf_url": rec["pdf_url"],
            "source": "ayuntamiento",
            "origen": "bandos_anuncios",
        }

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
        rows = self._collect_licencia_info()
        seen: set[str] = {r["id"] for r in rows}
        for rec in self._collect_bandos():
            lic = self._bandos_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento", "at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in self._collect_pgou():
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
        for rec in self._collect_bandos():
            proy = self._bandos_to_proyecto(rec)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento", "at": datetime.now(timezone.utc).isoformat()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
