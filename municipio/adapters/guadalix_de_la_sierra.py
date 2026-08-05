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

WEB_BASE = "https://www.guadalixdelasierra.com"
SEDE_BASE = "https://guadalixdelasierra.eadministracion.es"
MUNICIPIO = "Guadalix de la Sierra"
ID_PREFIX = "guadalix-de-la-sierra"

NNSS_URL = f"{WEB_BASE}/index.php/portal-de-transparencia/normas-subsidiarias"
ORDENACION_URL = (
    f"{WEB_BASE}/index.php/portal-de-transparencia/informacion-trasparencia/"
    "informacion-ordenacion-del-territorio"
)
BOCM_URL = f"{WEB_BASE}/index.php/portal-de-transparencia/publicaciones-en-boletines-oficiales"
MODELOS_URL = f"{WEB_BASE}/index.php/modelos-de-solicitud"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "GUADALIX DE LA SIERRA"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|obra)|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|calificaci[oó]n urban|"
    r"autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|primera ocupaci[oó]n|"
    r"cambio de uso|agrupaci[oó]n de terrenos|obras no sujetas)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|aprobaci[oó]n|reparcel|sector|"
    r"ordenaci[oó]n|suelo|bocm|servicios urban|"
    r"\b(?:UE|SAU|SG|PERI|S)-\d+[A-Z0-9-]*\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|juez de paz|notificaci[oó]n en procedimiento|"
    r"fiestas|calendario fiscal|cementerio|tanatorio|honores|veh[ií]culos|ibi|"
    r"farmacia|arquitecto municipal|plaza.*arquitecto|bonificaci[oó]n.*ibi|"
    r"animales potencialmente|empadronamiento|fraccionamiento.*deuda|enterramiento)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM = re.compile(r"BOCM\s*N[ºo°.]?\s*(\d+)\s+de\s+fecha\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.I)
RE_BOCM_SHORT = re.compile(r"BOCM\s*(?:N[úu]m\.?\s*)?(\d+).*?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.I)
RE_BOCM_NUM = re.compile(r"BOCM\s*(?:del?|N[ºo°.])\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


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
    for pat in (RE_BOCM, RE_BOCM_SHORT, RE_BOCM_NUM):
        m = pat.search(text or "")
        if m:
            groups = m.groups()
            try:
                if len(groups) == 4:
                    day, month_name, year = int(groups[1]), groups[2].lower(), int(groups[3])
                else:
                    day, month_name, year = int(groups[0]), groups[1].lower(), int(groups[2])
                month = MONTHS.get(month_name[:3] if month_name[:3] in MONTHS else month_name)
                if month:
                    return datetime(year, month, day).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bue-\d+\b", n):
        return "unidad de ejecución"
    if re.search(r"\bsau-\d+\b", n):
        return "sector de actuación urbanística"
    if re.search(r"\bsg\b", n) or "polígono ganadero" in n or "parque" in n:
        return "suelo genérico"
    if "peri" in n:
        return "PERI"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "ordenanza" in n and "urban" in n:
        return "ordenanza urbanística"
    if "bocm" in n:
        return "publicación BOCM"
    return "planeamiento"


class GuadalixDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla + Phoca Download + WFS SITCM (sede eAdmin SPA sin tablón scrapeable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.nnss_url = str(self.config.get("nnss_url") or NNSS_URL)
        self.ordenacion_url = str(self.config.get("ordenacion_url") or ORDENACION_URL)
        self.bocm_url = str(self.config.get("bocm_url") or BOCM_URL)
        self.modelos_url = str(self.config.get("modelos_url") or MODELOS_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadalix-de-la-sierra/1.0")},
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
        return urllib.parse.urljoin(f"{(base or WEB_BASE)}/", href)

    def _parse_phoca_boxes(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for box in re.findall(r'<div class="pd-filebox">(.*?)</div>\s*<div class="pd-cb">', html, re.S):
            title_m = re.search(r'<div class="pd-title">([^<]+)</div>', box)
            href_m = re.search(r'href="([^"]+)"', box)
            if not title_m or not href_m:
                continue
            titulo = _strip_html(title_m.group(1))
            url = self._abs_url(href_m.group(1), page_url)
            desc_m = re.search(r"pd-fdesc'&gt;&lt;p&gt;([^&]+)", box)
            descripcion = unescape(desc_m.group(1)) if desc_m else ""
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(f"{titulo} {descripcion}"),
                    "blob": f"{titulo} {descripcion} {url}",
                }
            )
        return rows

    def _collect_phoca_pages(self, base_url: str, max_pages: int = 6) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_idx in range(max_pages):
            url = base_url if page_idx == 0 else f"{base_url}?start={page_idx * 20}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            batch = self._parse_phoca_boxes(html, url)
            if not batch:
                break
            for row in batch:
                key = row["url"]
                if key not in seen:
                    seen.add(key)
                    rows.append({**row, "page_url": url})
        return rows

    def _wfs_query(self, cql: str, count: int = 120) -> list[dict[str, Any]]:
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

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(titulo or ""):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return None
        name = str(meta.get("ambito_name") or "")
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
        ) if name else ""
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                if cql
                else self.wfs_url
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": name or None,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
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
        for feat in feats:
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([feat])
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

    def _collect_info_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.nnss_url),
                "municipio": MUNICIPIO,
                "titulo": "Normas subsidiarias de urbanismo — visor SITCM",
                "fecha": None,
                "tipo": "normas subsidiarias",
                "url": self.nnss_url,
                "source": "ayuntamiento",
                "nota": "NNSS impuestas por la Comunidad de Madrid; visor cartográfico SITCM",
                "origen": "nnss_info",
            },
            {
                "id": _stable_id("proy", self.ordenacion_url),
                "municipio": MUNICIPIO,
                "titulo": "Información ordenación del territorio",
                "fecha": None,
                "tipo": "urbanismo",
                "url": self.ordenacion_url,
                "source": "ayuntamiento",
                "origen": "ordenacion_info",
            },
        ]

    def _phoca_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": origen,
        }
        if row.get("descripcion"):
            rec["descripcion"] = row["descripcion"]
        self._enrich_geometry(rec)
        return rec

    def _phoca_to_licencia(self, row: dict[str, Any], origen: str) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Formulario/modelo de solicitud",
            "origen": origen,
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.modelos_url),
                "fecha_concesion": None,
                "tipo": "modelos de solicitud urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Modelos de solicitud — urbanismo y licencias",
                "url": self.modelos_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF de trámites urbanísticos",
                "origen": "modelos_info",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/home",
                "source": "ayuntamiento",
                "nota": "SPA eAdmin; sin listado público de licencias concedidas",
                "origen": "sede_info",
            },
        ]

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_phoca_pages(self.modelos_url):
            rec = self._phoca_to_licencia(item, "modelos_phoca")
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "modelos_phoca"),
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_info_proyectos():
            add(rec)
        for item in self._collect_phoca_pages(self.bocm_url):
            add(self._phoca_to_proyecto(item, "bocm_phoca"))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "bocm_phoca": sum(1 for r in rows if r.get("origen") == "bocm_phoca"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
