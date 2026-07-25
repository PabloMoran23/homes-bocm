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
from municipio.geometry import geometry_centroid

BASE = "https://www.valladolid.gob.es"
SEDE_BASE = "https://sede.valladolid.es"
MUNICIPIO = "Valladolid"
ID_PREFIX = "valladolid"

TABLON_LIST = f"{BASE}/es/tablon-oficial/ayuntamiento-valladolid/anuncios-edictos"
TABLON_SEARCH = f"{BASE}/es/tablon-oficial/ayuntamiento-valladolid-tablon-oficial.buscar"
PLAI_BASE = "https://servicios.jcyl.es/PlanPublica"
PLAI_MUNICIPIO = 186
PLAI_PROVINCIA = 47

DEFAULT_TABLON_SEARCHES: list[tuple[str, str]] = [
    ("S_TEMA_EDICTO_min", "ANUNCIO DE INFORMACIÓN PÚBLICA"),
    ("text", "planeamiento"),
    ("text", "urbanismo"),
]

DEFAULT_DROUS_LAYERS: list[dict[str, Any]] = [
    {
        "year": 2026,
        "layer_id": 7,
        "url": "https://gisava.valladolid.es/server/rest/services/SDE_Drous_2026/FeatureServer/7",
    },
    {
        "year": 2025,
        "layer_id": 6,
        "url": "https://gisava.valladolid.es/server/rest/services/SDE_Drous_2025/FeatureServer/6",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|drou|obra|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|informaci[oó]n p[uú]blica|"
    r"exposici[oó]n p[uú]blica|actuaci[oó]n|gesti[oó]n urban|gerencia de urbanismo|"
    r"modificaci[oó]n.{0,40}(?:plan|pgou|urban)|licencia ambiental|audiencia|"
    r"ocupaci[oó]n.{0,20}v[ií]a p[uú]blica|aprobaci[oó]n inicial)",
)
RE_NOISE = re.compile(
    r"(?i)(tr[aá]fico|omu\b|multas? de|sancion|denuncias? de|proceso selectivo|"
    r"oposici[oó]n|empleo p[uú]blico|convocatoria.{0,30}(?:puesto|t[eé]cnico|funcionario|"
    r"libre designaci[oó]n|bolsa)|modificaci[oó]n de cr[eé]ditos|padr[oó]n|ivtm|"
    r"recaudaci[oó]n|notificaci[oó]n.{0,20}tr[aá]fico|disciplina vial)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _parse_epoch_ms(value: Any) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        ms = int(value)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _proyecto_tipo(title: str, tema: str = "") -> str:
    blob = f"{title} {tema}".lower()
    if "informaci" in blob or "exposici" in blob:
        return "información pública"
    if "plan parcial" in blob or "plan especial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "licencia ambiental" in blob:
        return "licencia ambiental"
    if "audiencia" in blob or "ocupaci" in blob:
        return "audiencia urbanística"
    if "pgou" in blob or "plan general" in blob or "planeam" in blob:
        return "planeamiento"
    if "actuaci" in blob:
        return "actuación urbanística"
    return "urbanismo"


class ValladolidAyuntamientoAdapter(AyuntamientoAdapter):
    """Tablón Proxia (proyectos/IP) + visor DROUS ArcGIS (licencias con geometría)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_timeout_s = int(self.config.get("tablon_timeout_s", 45))
        self.plai_max_pages = int(self.config.get("plai_max_pages", 12))
        self.plai_page_size = int(self.config.get("plai_page_size", 15))
        self.drous_page_size = int(self.config.get("drous_page_size", 1000))
        raw_searches = self.config.get("tablon_searches")
        if raw_searches:
            self.tablon_searches = [(s["param"], s["value"]) for s in raw_searches]
        else:
            self.tablon_searches = list(DEFAULT_TABLON_SEARCHES)
        geom_cfg = self.config.get("geometry") or {}
        raw_layers = geom_cfg.get("drous_layers") or self.config.get("drous_layers")
        if raw_layers:
            self.drous_layers = list(raw_layers)
        else:
            years = {int(y) for y in (self.config.get("drous_years") or [2026, 2025])}
            self.drous_layers = [layer for layer in DEFAULT_DROUS_LAYERS if int(layer["year"]) in years]

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        timeout_s: int | None = None,
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-valladolid/1.0")}
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s or 90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _safe_fetch(self, url: str, *, timeout_s: int | None = None) -> str | None:
        try:
            return self._fetch(url, timeout_s=timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valladolid/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _parse_tablon_items(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        start = html.find('<ul class="cmContentList')
        if start < 0:
            return rows
        end = html.find("</ul>", start)
        chunk = html[start:end] if end >= 0 else html[start:]
        for item in re.findall(r'<li class="cmContentItem[^"]*"[^>]*>(.*?)</li>', chunk, re.S):
            title_m = re.search(r'class="content-name-embedder"[^>]*>(.*?)</span>', item, re.S)
            link_m = re.search(r'href="([^"]+)" class="cmContentLink"', item)
            if not title_m or not link_m:
                continue
            title = _strip_html(title_m.group(1))
            url = link_m.group(1)
            if not url.startswith("http"):
                url = BASE + url
            rem_m = re.search(r"Remitente</dt><dd[^>]*>(.*?)</dd>", item, re.S)
            tema_m = re.search(r"Tema o categor[ií]a</dt><dd[^>]*>(.*?)</dd>", item, re.S)
            fecha_m = re.search(r'pval-s-fecha-publicacion">(\d+/\d+/\d+)', item)
            rows.append(
                {
                    "title": title,
                    "url": url,
                    "remitente": _strip_html(rem_m.group(1) if rem_m else ""),
                    "tema": _strip_html(tema_m.group(1) if tema_m else ""),
                    "fecha": fecha_m.group(1) if fecha_m else "",
                }
            )
        return rows

    def _search_tablon(self, param: str, value: str) -> list[dict[str, str]]:
        qs = urllib.parse.urlencode(
            {
                "formName": "searchForm",
                "searchType": "0",
                param: value,
            }
        )
        html = self._safe_fetch(f"{TABLON_SEARCH}?{qs}", timeout_s=self.tablon_timeout_s)
        if not html:
            return []
        return self._parse_tablon_items(html)

    def _plai_page_url(self, offset: int) -> str:
        params = {
            "pager.size": str(self.plai_page_size),
            "pager.reload": "no",
            "municipio": str(self.config.get("plai_municipio") or PLAI_MUNICIPIO),
            "provincia": str(self.config.get("plai_provincia") or PLAI_PROVINCIA),
            "urlResults": "searchVPubDocMuniPlai.do",
            "pager.offset": str(offset),
            "pager.sortindex": "3",
            "pager.sortname": "fPublicacion",
        }
        return f"{PLAI_BASE}/searchVPubDocMuniPlai.do?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_plai_rows(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[-2] if len(cells) >= 5 else cells[-1]
            if not titulo or titulo.lower().startswith("no hay documentos"):
                continue
            fecha = _parse_fecha_dmy(cells[2]) or cells[2]
            doc_m = re.search(r"doGoBoletin\('(\d+)'", tr) or re.search(
                r"doOpenDocumento\((\d+)\)", tr
            )
            doc_id = doc_m.group(1) if doc_m else titulo
            url = (
                f"{PLAI_BASE}/openDocumento.do?cDocId={doc_id}"
                if doc_m and "doOpenDocumento" in tr
                else f"{PLAI_BASE}/searchVPubDocMuniPlai.do?provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO}"
            )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": fecha or "",
                    "instrumento": cells[1] if len(cells) > 1 else "",
                    "origen": "plai_jcyl",
                }
            )
        return rows

    def _collect_plai_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(self.plai_max_pages):
            offset = page * self.plai_page_size
            html = self._safe_fetch(self._plai_page_url(offset), timeout_s=60)
            if not html:
                break
            parsed = self._parse_plai_rows(html)
            if not parsed:
                break
            for item in parsed:
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                fecha = _parse_fecha_dmy(item.get("fecha") or "") or item.get("fecha")
                rows.append(
                    {
                        "id": _stable_id("proy", item["url"] + item["title"]),
                        "municipio": MUNICIPIO,
                        "titulo": item["title"][:500],
                        "fecha": fecha,
                        "tipo": _proyecto_tipo(item["title"], item.get("instrumento", "")),
                        "url": item["url"],
                        "source": "ayuntamiento",
                        "origen": "plai_jcyl",
                        "instrumento": item.get("instrumento") or None,
                    }
                )
        return rows

    def _is_proyecto_row(self, row: dict[str, str]) -> bool:
        blob = f"{row['title']} {row['remitente']} {row['tema']}"
        if RE_NOISE.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob))

    def _row_to_proyecto(self, row: dict[str, str]) -> dict[str, Any]:
        fecha = _parse_fecha_dmy(row.get("fecha") or "") or _parse_fecha_dmy(row.get("title") or "")
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["title"][:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(row["title"], row.get("tema", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "remitente": row.get("remitente") or None,
            "tema_tablon": row.get("tema") or None,
        }

    def _collect_tablon_proyectos(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add_from_items(items: list[dict[str, str]]) -> None:
            for item in items:
                if not self._is_proyecto_row(item):
                    continue
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                rows.append(self._row_to_proyecto(item))

        for param, value in self.tablon_searches:
            add_from_items(self._search_tablon(param, value))

        html = self._safe_fetch(TABLON_LIST, timeout_s=self.tablon_timeout_s)
        if html:
            add_from_items(self._parse_tablon_items(html))

        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._collect_plai_proyectos():
            by_id[rec["id"]] = rec
        for rec in self._collect_tablon_proyectos():
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _drous_query_url(
        self,
        layer_url: str,
        *,
        offset: int,
        count: int,
        geometry: bool,
    ) -> str:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true" if geometry else "false",
            "f": "geojson" if geometry else "json",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(count),
            "orderByFields": "OBJECTID",
        }
        return f"{layer_url.rstrip('/')}/query?{urllib.parse.urlencode(params)}"

    def _drous_feature_to_licencia(
        self,
        feature: dict[str, Any],
        *,
        layer_url: str,
        query_url: str,
        year: int,
    ) -> dict[str, Any] | None:
        props = feature.get("properties") or {}
        exp = str(props.get("JOIN_NUMER") or props.get("REF_CATAST") or props.get("OBJECTID") or "").strip()
        if not exp:
            return None
        fecha = _parse_epoch_ms(props.get("FECHA_NUM")) or _parse_fecha_dmy(str(props.get("FECHA") or ""))
        titulo = str(props.get("OBJETO_DRO") or "DROU").strip()
        emplaz = str(props.get("EMPLAZAMIE") or "").strip()
        distrito = str(props.get("DISTRITO_T") or props.get("DISTRIT_PO") or "").strip() or None
        key = f"{year}:{exp}"
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha,
            "tipo": titulo[:200] if titulo else "DROU",
            "distrito": distrito,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "emplazamiento": emplaz or None,
            "expediente": exp,
            "url": (
                "https://gisava.valladolid.es/portal/apps/webappviewer/index.html?"
                f"id=c6d3c10df19b4e55a7badc021b51cfe1&exp={urllib.parse.quote(exp)}"
            ),
            "source": "ayuntamiento",
            "anio_drous": year,
        }
        geom = feature.get("geometry")
        if isinstance(geom, dict) and geom.get("type") in {"Polygon", "MultiPolygon"}:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_visor_arcgis"
            rec["geometry_source_url"] = query_url
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
                rec["coord_source"] = "portal_geometry_centroid"
        return rec

    def _collect_drous_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for layer in self.drous_layers:
            layer_url = str(layer["url"])
            year = int(layer.get("year") or 0)
            offset = 0
            while True:
                query_url = self._drous_query_url(
                    layer_url,
                    offset=offset,
                    count=self.drous_page_size,
                    geometry=True,
                )
                try:
                    payload = self._fetch_json(query_url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                features = payload.get("features") or []
                if not features:
                    break
                for feat in features:
                    rec = self._drous_feature_to_licencia(
                        feat,
                        layer_url=layer_url,
                        query_url=query_url,
                        year=year,
                    )
                    if rec and rec["id"] not in seen:
                        seen.add(rec["id"])
                        rows.append(rec)
                if len(features) < self.drous_page_size:
                    break
                offset += self.drous_page_size
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        """Páginas informativas de trámites urbanismo en sede (sin concesiones publicadas)."""
        rows = [
            {
                "id": _stable_id("lic", "sede-drou-menor"),
                "fecha_concesion": None,
                "tipo": "trámite DROU obra menor",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "DROU de obra menor y actos uso suelo sin proyecto",
                "url": f"{SEDE_BASE}/",
                "source": "ayuntamiento",
                "nota": "Trámite destacado sede; concesiones en visor DROUS",
            },
            {
                "id": _stable_id("lic", "sede-urbanismo"),
                "fecha_concesion": None,
                "tipo": "trámite urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "URBANISMO, LICENCIA DE OBRAS Y ACTIVIDADES",
                "url": f"{SEDE_BASE}/",
                "source": "ayuntamiento",
                "nota": "Catálogo sede; listado de concesiones en DROUS GIS",
            },
        ]
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_drous_licencias()
        if not rows:
            rows = self._collect_tramites_licencias()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "drous_arcgis" if with_geom else "sede_tramites",
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_drous_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        plai = sum(1 for r in rows if r.get("origen") == "plai_jcyl")
        tablon = len(rows) - plai
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "plai_tablon",
            "plai_rows": plai,
            "tablon_rows": tablon,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
