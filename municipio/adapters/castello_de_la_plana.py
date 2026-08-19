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

WEB_BASE = "https://www.castello.es"
SEDE_BASE = "https://sede.castello.es"
BOARD_URL = f"{SEDE_BASE}/board/"
GEOPORTAL_URL = (
    "https://castelloplana.maps.arcgis.com/apps/webappviewer/index.html"
    "?id=64f1eda0cc0640e68e920ccf94c58cfc"
)
ARCGIS_FS = (
    "https://services-eu1.arcgis.com/BkKDpc83GzZpJjXP/arcgis/rest/services/"
    "Geoportal_Urban%C3%ADstico_WFL1/FeatureServer"
)
MUNICIPIO = "Castelló de la Plana"
ID_PREFIX = "castello-de-la-plana"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|centro de ocio)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|expropiaci[oó]n|unidad de ejecuci[oó]n|"
    r"actuaci[oó]n aislada|plan especial|geoportal)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvencion|subvenci[oó]n|bomber|ocupaci[oó]n p[uú]blica|ordenanza (?!urban)|"
    r"protecci[oó]n de la legalidad ambiental)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://(?:sede\.castello\.es|castello\.sedelectronica\.es))?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, procedimiento: str = "", tipo_gis: str = "") -> str:
    blob = f"{title} {procedimiento} {tipo_gis}".lower()
    if "plan especial" in blob or "pe-" in blob:
        return "plan especial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or "sector" in blob or blob.startswith("st ") or blob.startswith("sr "):
        return "sector planeamiento"
    if "pge" in blob or "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "expropiaci" in blob:
        return "expropiación"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "licencia" in blob:
        return "licencia publicada"
    return "planeamiento"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        gtype = g.get("type")
        coords = g.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class CastelloDeLaPlanaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay (bloqueado CI) + sede espublico + Geoportal ArcGIS (ámbitos PGOU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.geoportal_url = str(self.config.get("geoportal_url") or GEOPORTAL_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.arcgis_fs = str(geom_cfg.get("base_url") or ARCGIS_FS).rstrip("/")
        self.arcgis_layer_id = int(geom_cfg.get("layer_id", 15))
        self.arcgis_name_field = str(geom_cfg.get("name_field") or "NOMBRE")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castello-de-la-plana/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castello-de-la-plana/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_gis_ambitos(self) -> list[dict[str, Any]]:
        field = self.arcgis_name_field
        where = f"{field} IS NOT NULL AND {field} <> ' ' AND {field} <> ''"
        offset = 0
        grouped: dict[str, list[dict[str, Any]]] = {}
        meta: dict[str, dict[str, Any]] = {}

        while True:
            params = {
                "where": where,
                "outFields": f"{field},TIPO_,CATEGORIA_,LAYER,SUPERFICIE,ID",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
                "resultOffset": str(offset),
                "resultRecordCount": "2000",
            }
            url = f"{self.arcgis_fs}/{self.arcgis_layer_id}/query?" + urllib.parse.urlencode(params)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                break

            batch = data.get("features") or []
            if not batch:
                break

            for feat in batch:
                props = feat.get("properties") or {}
                name = _strip_html(str(props.get(field) or ""))
                if not name:
                    continue
                grouped.setdefault(name, []).append(feat)
                if name not in meta:
                    meta[name] = props

            if len(batch) < 2000:
                break
            offset += 2000

        rows: list[dict[str, Any]] = []
        for name, feats in grouped.items():
            geom = _merge_geometries(feats)
            props = meta.get(name) or {}
            query_url = (
                f"{self.arcgis_fs}/{self.arcgis_layer_id}/query?"
                + urllib.parse.urlencode(
                    {
                        "where": f"{field}='{name.replace(chr(39), chr(39)+chr(39))}'",
                        "outFields": "*",
                        "returnGeometry": "true",
                        "f": "geojson",
                        "outSR": "4326",
                    }
                )
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"gis:{name}"),
                "municipio": MUNICIPIO,
                "titulo": name,
                "fecha": None,
                "tipo": _proyecto_tipo(name, tipo_gis=str(props.get("TIPO_") or "")),
                "url": self.geoportal_url,
                "source": "ayuntamiento",
                "origen": "geoportal_arcgis",
                "categoria_gis": props.get("CATEGORIA_"),
                "tipo_gis": props.get("TIPO_"),
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_visor_arcgis"
                rec["geometry_source_url"] = query_url
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _collect_info_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.geoportal_url),
                "municipio": MUNICIPIO,
                "titulo": "Geoportal Urbanístico — PGOU Castelló de la Plana",
                "fecha": None,
                "tipo": "visor planeamiento",
                "url": self.geoportal_url,
                "source": "ayuntamiento",
                "origen": "geoportal_info",
            },
            {
                "id": _stable_id("proy", f"{WEB_BASE}/es/urbanismo-y-planificacion-urbana"),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo y Planificación Urbana — Ayuntamiento",
                "fecha": None,
                "tipo": "planeamiento",
                "url": f"{WEB_BASE}/es/urbanismo-y-planificacion-urbana",
                "source": "ayuntamiento",
                "origen": "web_urbana",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede electrónica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genérico")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "genérico" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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

        for rec in self._collect_gis_ambitos():
            add(rec)
        for rec in self._collect_info_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "geoportal": sum(1 for r in rows if r.get("origen") == "geoportal_arcgis"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
