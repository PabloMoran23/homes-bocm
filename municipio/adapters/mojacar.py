from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://ayuntamientomojacar.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "http://ayuntamiento.mojacar.es"
URBANISMO_URL = f"{WEB_BASE}/informacion/urbanismo"
PGOU_VISOR_URL = "https://palcos.tcasa.es/PGOUMojacar/"
MUNICIPIO = "Mojácar"
ID_PREFIX = "mojacar"
COD_INE = "04057"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|enajenaci[oó]n.*parcela)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|transf(?:erencia)? urban|actuaci[oó]n|delimitaci[oó]n|"
    r"anteproyecto|variante|paseo mar|edar|residencia|desglosado|visado)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"oferta empleo p[uú]blico|plan de igualdad|junta de gobierno local|"
    r"convocatoria de la junta|convocatoria de el pleno|decreto.*convocatoria|"
    r"ayudas presentada por gdr|educaci[oó]n infantil|administraci[oó]n electr[oó]nica)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ayuntamientomojacar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "transf" in b and "urban" in b:
        return "transformación urbanística"
    if "anteproyecto" in b:
        return "anteproyecto"
    if "paseo mar" in b:
        return "proyecto infraestructura"
    if "residencia" in b or "edar" in b:
        return "proyecto equipamiento"
    return "urbanismo"


class MojacarAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico (tablón) + web cmsdipro Diputación Almería + WFS sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.pgou_visor_url = str(self.config.get("pgou_visor_url") or PGOU_VISOR_URL)
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mojacar/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mojacar/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, page_url: str = WEB_BASE) -> str:
        return urljoin(page_url, href)

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

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        cql = urllib.parse.quote(f"cod_ine='{self.cod_ine}'")
        url = (
            "https://app.dipalme.org/geoserver/urbanismo/ows?"
            "service=WFS&version=2.0.0&request=GetFeature&"
            "typeName=urbanismo:v_siu_ambitos_o_sectores&"
            f"CQL_FILTER={cql}&"
            "outputFormat=application/json&srsName=EPSG:4326"
        )
        try:
            data = self._fetch_json(url)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": _norm_text(sector),
                        "geom": geom,
                        "clase_suelo": props.get("clase_suelo"),
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        result: dict[str, Any] | None = None
        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            if len(sector_norm) < 3:
                continue
            if sector_norm in title_norm or re.search(rf"\b{re.escape(sector_norm)}\b", title_norm):
                geom = row["geom"]
                sector_escaped = row["sector"].replace("'", "''")
                cql = urllib.parse.quote(
                    f"cod_ine='{self.cod_ine}' AND sector='{sector_escaped}'"
                )
                query = (
                    "https://app.dipalme.org/geoserver/urbanismo/ows?"
                    "service=WFS&version=2.0.0&request=GetFeature&"
                    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                    f"CQL_FILTER={cql}&"
                    "count=1&outputFormat=application/json&srsName=EPSG:4326"
                )
                result = {
                    "geom_geojson": geom,
                    "geometry_source": "dipalme_wfs_sector",
                    "geometry_source_url": query,
                    "coord_source": "portal_geometry_centroid",
                    "sector_urbanistico": row["sector"],
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    result["lat"], result["lon"] = centroid
                break

        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry_for_title(rec.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos de licencias y actuaciones en sede espublico",
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
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
        ]

    def _collect_urbanismo_links(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return rows

        idx = html.lower().find("plan general de orden")
        chunk = html[idx:] if idx >= 0 else html

        for m in RE_LINK.finditer(chunk):
            href = m.group(1).replace("&amp;", "&")
            title = _strip_html(m.group(2))
            if not title or len(title) < 4:
                continue
            url = self._abs_url(href, self.urbanismo_url)
            if url in seen:
                continue
            blob = f"{title} {url}"
            if not RE_PROYECTO.search(blob):
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": url,
                    "blob": blob,
                    "origen": "web_urbanismo",
                }
            )
        return rows

    def _collect_pgou_visor(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.pgou_visor_url),
            "municipio": MUNICIPIO,
            "titulo": "Visor online PGOU Mojácar (palcos/tcasa)",
            "fecha": None,
            "tipo": "PGOU",
            "url": self.pgou_visor_url,
            "source": "ayuntamiento",
            "origen": "visor_pgou",
            "nota": "GeoServer WMS; WFS deshabilitado — sin polígono por expediente",
        }

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "actuaciones")):
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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc:
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
            "origen": "tablon",
        }
        return self._enrich_geometry(rec)

    def _urbanismo_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item.get("blob") or item["titulo"]),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen", "web_urbanismo"),
        }
        return self._enrich_geometry(rec)

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

        add(self._collect_pgou_visor())
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_urbanismo_links():
            add(self._urbanismo_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
            "visor": sum(1 for r in rows if r.get("origen") == "visor_pgou"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
