from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
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

WEB_BASE = "https://www.pelayosdelapresa.es"
SEDE_BASE = "https://pelayospresa.sedelectronica.es"
MUNICIPIO = "Pelayos de la Presa"
ID_PREFIX = "pelayos-de-la-presa"

ORDENANZAS_URL = f"{WEB_BASE}/ayuntamiento/normativa-municipal/ordenanzas-reguladoras"
SOLICITUDES_URL = f"{WEB_BASE}/tramites/solicitudes"
AYUDA_URL = f"{WEB_BASE}/ayuda-ciudadana"
CM_PLANEAMIENTO_URL = (
    "https://www.comunidad.madrid/servicios/urbanismo/"
    "registro-documentos-urbanisticos-municipales"
)
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "PELAYOS DE LA PRESA"

DEFAULT_LICENCIA_DOCS: list[dict[str, str]] = [
    {
        "path": "/images/articulos/solicitudes/1_Solicitud_general.pdf",
        "tipo": "solicitud general",
        "titulo": "Solicitud general",
    },
    {
        "path": "/images/articulos/solicitudes/031_Declaracin_Responsable_Urbanstica_con_autoliquidacin_y_fianza_comp",
        "tipo": "declaración responsable urbanística",
        "titulo": "Declaración responsable urbanística",
    },
    {
        "path": "/images/articulos/solicitudes/032_Solicitud_de_Licencia_Urbanstica_con_autoliquidacin_y_fianza_compr",
        "tipo": "solicitud licencia urbanística",
        "titulo": "Solicitud de licencia urbanística",
    },
    {
        "path": "/images/articulos/solicitudes/034_Solicitud_de_Cdula_Urbanstica.pdf",
        "tipo": "cédula urbanística",
        "titulo": "Solicitud de cédula urbanística",
    },
    {
        "path": "/images/articulos/ordenanzas_reguladoras/15_ORDENANZA_REGULADORA_DEL_REGIMEN__DE_LICENCIA_Y_DECLARAC",
        "tipo": "ordenanza licencias urbanísticas",
        "titulo": "Ordenanza reguladora del régimen de licencia y declaración responsable",
    },
]

RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_PREVIEW = re.compile(
    r'href="(https://pelayospresa\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|c[eé]dula urban|vallado|limpieza de (?:solares|parcelas))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"estudio de detalle|modificaci[oó]n puntual|sector|arbolado|parcela|"
    r"residuos.*construc|limpieza.*parcela|ordenanza.*urban|"
    r"\bua[\-\s]*\d+\b|unidad de actuaci[oó]n|sitcm)",
)
RE_SKIP = re.compile(
    r"(?i)(presupuesto|modificaci[oó]n (?:de )?cr[eé]dito|calendario fiscal|"
    r"cobranza.*iae|impuesto sobre actividades|convocatoria.*pleno|"
    r"empleo[- ]formaci[oó]n|subvenci[oó]n|justificante ausencia|incendio|"
    r"nombramiento|padr[oó]n|ivtm|tarjeta de estacionamiento|perros peligros)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _abs_url(href: str, base: str = WEB_BASE) -> str:
    return urllib.parse.urljoin(f"{base}/", unescape(href).replace("&amp;", "&").strip())


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bua[\-\s]*\d+\b", n):
        return "unidad de actuación"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "plan general" in n or "pgou" in n:
        return "planeamiento"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "informaci" in n:
        return "información pública"
    if "arbolado" in n:
        return "ordenanza arbolado"
    if "parcela" in n or "limpieza" in n or "vallado" in n:
        return "ordenanza parcelas"
    if "sitcm" in n:
        return "planeamiento"
    return "urbanismo"


class PelayosDeLaPresaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla web + sede espublico gestiona + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.solicitudes_url = str(self.config.get("solicitudes_url") or SOLICITUDES_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pelayos-de-la-presa/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _parse_page_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LINK.finditer(html):
            href, title = m.group(1), unescape(m.group(2).strip())
            if not title or len(title) < 8:
                continue
            doc_url = _abs_url(href)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            blob = f"{title} {doc_url}"
            if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": page_url,
                    "doc_url": doc_url,
                    "fecha": _parse_fecha_dmy(blob),
                    "blob": blob,
                }
            )
        return rows

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
                "count": "100",
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
        feat = self._load_sitcm_ambitos().get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        esc = ambit_name.replace("'", "''")
        cql = f"DS_MUNICIPIO='{self.wfs_municipio}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "5",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?{params}",
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
        title_up = title.upper()
        for ambit_name in self._load_sitcm_ambitos():
            compact = ambit_name.replace("-", "").replace(" ", "")
            if ambit_name in title_up or compact in title_up.replace(" ", ""):
                return self._geometry_from_ambit(ambit_name)
        return None

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

    def _collect_ordenanzas_proyectos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ordenanzas_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._parse_page_links(html, self.ordenanzas_url):
            if RE_SKIP.search(item["blob"]) and not RE_PROYECTO.search(item["blob"]):
                continue
            if not RE_PROYECTO.search(item["blob"]):
                continue
            row: dict[str, Any] = {
                "id": _stable_id("proy", item["doc_url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": item.get("fecha"),
                "tipo": _proyecto_tipo(item["titulo"]),
                "url": self.ordenanzas_url,
                "doc_url": item["doc_url"],
                "source": "ayuntamiento",
                "origen": "ordenanzas_reguladoras",
            }
            self._attach_geometry(row)
            rows.append(row)
        return rows

    def _collect_sitcm_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ambit_name, feat in self._load_sitcm_ambitos().items():
            merged = _merge_geometries([feat])
            if not merged:
                continue
            titulo = f"Ámbito planeamiento SITCM — {ambit_name}"
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"sitcm-{ambit_name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": None,
                "tipo": _proyecto_tipo(ambit_name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_ambito",
            }
            geom = self._geometry_from_ambit(ambit_name)
            if geom:
                row.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    row["lat"], row["lon"] = centroid
            rows.append(row)
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", CM_PLANEAMIENTO_URL),
                "municipio": MUNICIPIO,
                "titulo": "Registro documentos urbanísticos municipales — Comunidad de Madrid (Pelayos de la Presa)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": CM_PLANEAMIENTO_URL,
                "source": "ayuntamiento",
                "origen": "cm_planeamiento",
                "nota": "Enlace desde ayuda-ciudadana; NNSS, modificaciones y planes parciales",
            },
            {
                "id": _stable_id("proy", SITCM_VISOR_URL),
                "municipio": MUNICIPIO,
                "titulo": "Visor cartográfico SITCM — planeamiento Comunidad de Madrid",
                "fecha": None,
                "tipo": "planeamiento",
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_visor",
            },
        ]

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if tbody_m:
            for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.I | re.S):
                row_html = row_m.group(1)
                if "emptyRow" in row_html:
                    continue
                cells: dict[str, str] = {}
                doc_url = self.board_url
                for cm in RE_BOARD_CELL.finditer(row_html):
                    label, val = cm.group(1), cm.group(2)
                    link_m = re.search(r'href="([^"]+)"', val, re.I)
                    if link_m:
                        doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                    cells[label] = _strip_html(val)
                titulo = cells.get("Descripción") or cells.get("Documento") or ""
                if not titulo:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": cells.get("Expediente", ""),
                        "procedimiento": cells.get("Procedimiento", ""),
                        "categoria": cells.get("Categoría", ""),
                        "descripcion": titulo,
                        "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                        "url": doc_url,
                        "origen": "sede_board",
                    }
                )
        if not rows:
            for m in RE_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 300) : m.end() + 100]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1).strip()) if title_m else url
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "descripcion": titulo,
                        "fecha": _parse_fecha_dmy(titulo),
                        "url": url,
                        "origen": "sede_board",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_docs") or DEFAULT_LICENCIA_DOCS:
            doc_url = _abs_url(str(item["path"]))
            rows.append(
                {
                    "id": _stable_id("lic", doc_url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario u ordenanza; no concesión publicada",
                    "origen": "web_tramites",
                }
            )
        try:
            html = self._fetch(self.solicitudes_url)
            for item in self._parse_page_links(html, self.solicitudes_url):
                if not RE_LICENCIA.search(item["blob"]):
                    continue
                doc_url = item["doc_url"]
                rows.append(
                    {
                        "id": _stable_id("lic", doc_url),
                        "fecha_concesion": None,
                        "tipo": _proyecto_tipo(item["titulo"]),
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": item["titulo"],
                        "url": doc_url,
                        "source": "ayuntamiento",
                        "nota": "Impreso descargable; no concesión publicada",
                        "origen": "web_tramites",
                    }
                )
        except urllib.error.URLError:
            pass
        rows.extend(
            [
                {
                    "id": _stable_id("lic", self.board_url),
                    "fecha_concesion": None,
                    "tipo": "tablón licencias urbanísticas",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Tablón de anuncios — sede electrónica",
                    "url": self.board_url,
                    "source": "ayuntamiento",
                    "nota": "Anuncios vigentes en espublico gestiona",
                    "origen": "sede_tablon",
                },
                {
                    "id": _stable_id("lic", f"{self.sede_base}/transparency/"),
                    "fecha_concesion": None,
                    "tipo": "transparencia urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Portal transparencia — urbanismo y obras públicas",
                    "url": f"{self.sede_base}/transparency/",
                    "source": "ayuntamiento",
                    "nota": "Sección 7 URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE",
                    "origen": "sede_transparency",
                },
            ]
        )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info()
        seen: set[str] = {r["id"] for r in rows}
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
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
        for row in (
            self._collect_sitcm_proyectos()
            + self._collect_ordenanzas_proyectos()
            + self._collect_static_proyectos()
        ):
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
        for item in self._collect_board():
            proy = self._board_to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
