from __future__ import annotations

import csv
import hashlib
import http.cookiejar
import io
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

SEDE_BASE = "https://puertollano.sedelectronica.es"
WEB_BASE = "https://www.puertollano.es"
DATOS_OBRAS_CSV = (
    "https://datosabiertos.puertollano.es/dataset/26778018-9e2b-440c-8f84-d14d96b4ebd7/"
    "resource/76b6aec2-b147-42d0-a974-e0fbe58d3588/download/obras.csv"
)
CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)
MUNICIPIO = "Puertollano"
ID_PREFIX = "puertollano"
INE_MUN = "13071"

RE_PREVIEW = re.compile(
    r'href="(https://puertollano\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://puertollano\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|ocupaci[oó]n (?:de |en )?v[ií]a|recepci[oó]n de obra|"
    r"segregaci[oó]n|agrupaci[oó]n de parcelas)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|actuaci[oó]n urban|modificaci[oó]n.*planeam|"
    r"aprobaci[oó]n.*planeam|certificado.*urban|informe urban|ordenanza|"
    r"reparcel|sector|fotov|solar|climatizaci[oó]n|urbanizaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|"
    r"vehiculos|notificaci[oó]n expediente|igualdad|"
    r"cobranza|iae|ivtm|cementerio|"
    r"calendario fiscal|recaudaci[oó]n|"
    r"fiestas|cine|empleo|deporte|pilates|gimnasia|"
    r"electores|bizum|caixabank|ofibus|ofimovil|horario.*l[ií]nea|"
    r"polic[ií]a local|proceso selectivo|oposici[oó]n|"
    r"animales potencialmente peligrosos|auto-?taxi|veh[ií]culo|herederos|"
    r"providencia de apremio|edicto.*apremio)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
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
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_coord_pair(text: str) -> tuple[float, float] | None:
    if not text:
        return None
    parts = re.split(r"[,;]", text.strip())
    if len(parts) < 2:
        return None
    try:
        a, b = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None
    if abs(a) <= 90 and abs(b) <= 180:
        return a, b
    if abs(b) <= 90 and abs(a) <= 180:
        return b, a
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "fotov" in n or "solar" in n:
        return "instalación fotovoltaica"
    if "planeamiento general" in n or "pgou" in n:
        return "planeamiento general"
    if "modificaci" in n and "planeam" in n:
        return "modificación planeamiento"
    if "urbaniz" in n or "reparcel" in n:
        return "urbanización / reparcelación"
    if "licencia" in n and "obra" in n:
        return "licencia de obra"
    if "carril bici" in n or "obra" in n:
        return "obra pública municipal"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra mayor" in n:
        return "licencia de obra mayor"
    if "obra menor" in n or "declaraci" in n:
        return "declaración responsable / obra menor"
    if "segregaci" in n or "agrupaci" in n:
        return "segregación / agrupación parcelas"
    if "actividad" in n:
        return "licencia de actividad"
    return "trámite licencia urbanística"


class PuertollanoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + datos abiertos Obras (CKAN) + PGOU CLM ArcGIS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.obras_csv_url = str(self.config.get("obras_csv_url") or DATOS_OBRAS_CSV)
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or INE_MUN)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-puertollano/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-puertollano/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0]) if cells else ""
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            expediente = _strip_html(cells[1]) if len(cells) > 1 else ""
            procedimiento = _strip_html(cells[2]) if len(cells) > 2 else ""
            categoria = _strip_html(cells[3]) if len(cells) > 3 else ""
            descripcion = _strip_html(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _strip_html(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info.0", "info_tablon")):
            try:
                html = self._fetch(url, timeout=45)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, timeout=25)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = href if href.startswith("http") else f"{self.sede_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_obras(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch_bytes(self.obras_csv_url, timeout=60)
        except urllib.error.URLError:
            return []
        text = raw.decode("utf-8", errors="replace")
        if text.startswith("\ufeff"):
            text = text[1:]
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        rows: list[dict[str, Any]] = []
        for row in reader:
            if not row:
                continue
            denom = (row.get("denominacion") or row.get("descripcion") or "").strip()
            if not denom:
                continue
            coords = _parse_coord_pair(row.get("coordenadas") or "")
            lat, lon = (coords[0], coords[1]) if coords else (None, None)
            fecha = (
                _parse_fecha_dmy(row.get("fecha_adjudicacion") or "")
                or _parse_fecha_dmy(row.get("fecha_inicio") or "")
                or _parse_fecha_dmy(row.get("fecha_licitacion") or "")
            )
            expte = (row.get("expediente") or row.get("expediente2") or "").strip() or None
            rows.append(
                {
                    "id_obra": row.get("id") or denom,
                    "titulo": denom[:500],
                    "descripcion": (row.get("descripcion") or "")[:500],
                    "zona": (row.get("zona_barrio") or "").strip() or None,
                    "estado": (row.get("estado") or "").strip() or None,
                    "direccion": (row.get("direccion") or "").strip() or None,
                    "tipo_obra": (row.get("tipo_obra") or "").strip() or None,
                    "expediente": expte,
                    "fecha": fecha,
                    "lat": lat,
                    "lon": lon,
                    "area": (row.get("area") or "").strip() or None,
                    "url": self.obras_csv_url,
                    "origen": "datos_abiertos_obras",
                }
            )
        return rows

    def _fetch_clm_pgou(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if self._pgou_geom is not None:
            return self._pgou_geom, self._pgou_meta
        where = f"COD_INE='{self.cod_ine}'"
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "NOM_PLAN,PLAN_,FECHA_APRO,DESCARGA",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            }
        )
        url = f"{self.clm_layer}/query?{params}"
        try:
            raw = self._fetch_bytes(url, timeout=90)
            data = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        features = data.get("features") or []
        if not features:
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        feat = features[0]
        geom = feat.get("geometry")
        props = feat.get("properties") or {}
        if not isinstance(geom, dict) or not geom.get("type"):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        self._pgou_geom = geom
        self._pgou_meta = {
            "nom_plan": props.get("NOM_PLAN"),
            "plan_code": props.get("PLAN_"),
            "descarga": props.get("DESCARGA"),
            "geometry_source_url": url,
        }
        return self._pgou_geom, self._pgou_meta

    def _pgou_proyecto_row(self) -> dict[str, Any] | None:
        geom, meta = self._fetch_clm_pgou()
        if not geom or not meta:
            return None
        nom = str(meta.get("nom_plan") or "Plan General de Ordenación Urbana")
        url = str(meta.get("descarga") or f"{self.web_base}/")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"pgou-clm-{self.cod_ine}"),
            "municipio": MUNICIPIO,
            "titulo": f"{nom} — {MUNICIPIO} (CLM)",
            "fecha": None,
            "tipo": "PGOU",
            "url": url,
            "source": "ayuntamiento",
            "origen": "clm_arcgis",
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": meta.get("geometry_source_url"),
            "coord_source": "portal_geometry_centroid",
        }
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid
        return rec

    def _attach_pgou_if_plan(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            g = record_geometry(rec) or {}
            if str(g.get("type") or "") in {"Polygon", "MultiPolygon"}:
                return
        blob = (rec.get("titulo") or "").lower()
        if "pgou" not in blob and "plan general" not in blob:
            return
        geom, meta = self._fetch_clm_pgou()
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = (meta or {}).get("geometry_source_url")
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas en sede espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — licencias y urbanismo",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Catálogo espublico (licencias de obra, actividad, etc.)",
                "origen": "dossier",
            },
            {
                "id": _stable_id("lic", self.obras_csv_url),
                "fecha_concesion": None,
                "tipo": "datos abiertos obras municipales",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Conjunto de datos Obras (CKAN)",
                "url": self.obras_csv_url,
                "source": "ayuntamiento",
                "nota": "CSV con expedientes y coordenadas de obras públicas (área URBANISMO)",
                "origen": "datos_abiertos",
            },
        ]

    def _should_exclude(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob):
            if RE_PROYECTO.search(blob) and (
                "ordenanza" in blob.lower() or "urban" in blob.lower() or "licencia" in blob.lower()
            ):
                return False
            return True
        return False

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if self._should_exclude(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if self._should_exclude(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        cat = (row.get("categoria") or "").lower()
        if cat not in ("urbanismo", "ordenanzas y reglamentos") and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _parse_fecha_dmy(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_pgou_if_plan(rec)
        return rec

    def _obra_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        if row.get("descripcion") and row["descripcion"] not in titulo:
            titulo = f"{titulo} — {row['descripcion']}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"obra-{row.get('id_obra')}-{row.get('expediente') or titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": row.get("url") or self.obras_csv_url,
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen"),
            "distrito": row.get("zona"),
            "direccion": row.get("direccion"),
            "estado_obra": row.get("estado"),
            "tipo_obra": row.get("tipo_obra"),
        }
        if row.get("lat") is not None and row.get("lon") is not None:
            rec["lat"] = row["lat"]
            rec["lon"] = row["lon"]
            rec["coordinates_crs"] = "EPSG:4326"
            rec["coord_source"] = "datos_abiertos_obras"
        return rec

    def _obra_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        expte = row.get("expediente")
        if not expte:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", f"obra-expte-{expte}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo_obra") or "obra pública / expediente urbanismo",
            "distrito": row.get("zona"),
            "titulo": row["titulo"],
            "expte": expte,
            "url": row.get("url") or self.obras_csv_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("lat") is not None and row.get("lon") is not None:
            rec["lat"] = row["lat"]
            rec["lon"] = row["lon"]
            rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        if self._should_exclude(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if self._should_exclude(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|urban|certificado|informe|actuaci", row["titulo"]
        ):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
        }
        self._attach_pgou_if_plan(rec)
        return rec

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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_obras():
            if (item.get("area") or "").upper() != "URBANISMO":
                continue
            rec = self._obra_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "obras": sum(1 for r in rows if r.get("origen") == "datos_abiertos_obras"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_obras():
            if (item.get("area") or "").upper() != "URBANISMO":
                continue
            rec = self._obra_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        after = len(rows)
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

        add(self._pgou_proyecto_row())
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_obras():
            add(self._obra_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "clm_pgou": sum(1 for r in rows if r.get("origen") == "clm_arcgis"),
            "obras": sum(1 for r in rows if r.get("origen") == "datos_abiertos_obras"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
