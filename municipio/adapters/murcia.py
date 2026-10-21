from __future__ import annotations

import hashlib
import json
import re
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
from shapely.geometry import shape

WEB_BASE = "https://www.murcia.es"
SEDE_BASE = "https://sede.murcia.es"
INFOURB_BASE = "http://urbanismo.murcia.es/infourb"

TABLON_URL = f"{SEDE_BASE}/tablon-de-anuncios"
ULTIMAS_URL = f"{INFOURB_BASE}/Ultimas.aspx"
URBANISMO_TRAMITES_URL = f"{SEDE_BASE}/ficha-categoria/10001"
LICENCIA_ORDINARIA_URL = f"{SEDE_BASE}/ficha-procedimiento/263"
LICENCIA_OBRA_MENOR_URL = f"{SEDE_BASE}/ficha-procedimiento/5422"

WFS_SECTORS_URL = (
    "https://callejero.murcia.es/wfs?"
    "service=WFS&version=1.1.0&request=GetFeature&"
    "typeName=urbanismo:sectores&"
    "outputFormat=application/json&srsName=EPSG:4326&maxFeatures=5000"
)

MUNICIPIO = "Murcia"
ID_PREFIX = "murcia"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n previa|c[eé]dula urban|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|director)|pgou|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|aprobaci[oó]n (?:inicial|definitiva|provisional)|urbanizaci[oó]n|"
    r"delimitaci[oó]n|avance|ordenaci[oó]n|sector|figura:|peri-|pe |reordenaci)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(sorteo|subvenci[oó]n|empleo p[uú]blico|proceso selectivo|becas|"
    r"bonotaxi|pad[ró]n|ordenanza reguladora del padr[oó]n|certamen municipal creamurcia|"
    r"club de idiomas|herederos|venta ambulante de flores|barras en navidad)",
)
RE_SECTOR_CODE = re.compile(
    r"\b([A-Z]{1,3}(?:-[A-Z0-9]+){1,8})\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TABLON_PAGER_LAST = re.compile(r'href="\?page=(\d+)"[^>]*class="page-link"[^>]*>\s*\d+\s*</a>', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_datetime_attr(value: str) -> str | None:
    if not value:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return str(max(years))
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b or " pp " in f" {b} ":
        return "plan parcial"
    if "plan especial" in b or " p.e." in b:
        return "plan especial"
    if "modificaci" in b and ("pgou" in b or "pgmo" in b or "plan general" in b):
        return "modificación PGOU"
    if "reparcel" in b:
        return "reparcelación"
    if "urbanizaci" in b:
        return "urbanización"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "avance" in b:
        return "avance planeamiento"
    if "reordenaci" in b:
        return "reordenación urbana"
    return "urbanismo"


class MurciaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Drupal (tablón) + infourb (últimas publicaciones) + WFS sectores PGMO."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 8))
        self._sector_by_code: dict[str, dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-murcia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-murcia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, page_url: str = SEDE_BASE) -> str:
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

    def _load_sectors(self) -> dict[str, dict[str, Any]]:
        if self._sector_by_code is not None:
            return self._sector_by_code
        mapping: dict[str, dict[str, Any]] = {}
        try:
            data = self._fetch_json(WFS_SECTORS_URL)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                code = str(props.get("nombre_cod") or "").strip()
                if not code or not isinstance(geom, dict):
                    continue
                if not shape(geom).is_valid:
                    continue
                key = _norm_text(code)
                if key not in mapping:
                    mapping[key] = {
                        "code": code,
                        "geom": geom,
                        "clase_suel": props.get("clase_suel"),
                    }
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            mapping = {}
        self._sector_by_code = mapping
        return mapping

    def _sector_codes_in_text(self, text: str) -> list[str]:
        title_norm = _norm_text(text)
        found: list[str] = []
        sectors = self._load_sectors()
        for m in RE_SECTOR_CODE.finditer(title_norm):
            cand = m.group(1)
            if len(cand) < 6 or "-" not in cand:
                continue
            if cand in sectors:
                found.append(cand)
        # longest match first (e.g. ZM-SS1-1 before ZM)
        found.sort(key=len, reverse=True)
        out: list[str] = []
        seen: set[str] = set()
        for c in found:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        result: dict[str, Any] | None = None
        sectors = self._load_sectors()
        for code in self._sector_codes_in_text(title):
            row = sectors.get(code)
            if not row:
                continue
            cql = urllib.parse.quote(f"nombre_cod='{row['code'].replace(chr(39), chr(39)+chr(39))}'")
            query = (
                "https://callejero.murcia.es/wfs?"
                "service=WFS&version=1.1.0&request=GetFeature&"
                "typeName=urbanismo:sectores&"
                f"CQL_FILTER={cql}&"
                "outputFormat=application/json&srsName=EPSG:4326&maxFeatures=1"
            )
            geom = row["geom"]
            result = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_source": "portal_wfs",
                "geometry_source_url": query,
                "coord_source": "portal_geometry_centroid",
                "sector_urbanistico": row["code"],
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
        blob = f"{rec.get('titulo', '')} {rec.get('expediente', '')}"
        geom_fields = self._fetch_geometry_for_title(blob)
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _parse_tablon_cards(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in re.findall(r'<div class="card mb-3">(.*?)</div>\s*</div>\s*</div>\s*</div>', html, re.S):
            dt_m = re.search(r'<time datetime="([^"]+)"', block)
            title_m = re.search(r'<p class="fw-bold">\s*(.*?)\s*</p>', block, re.S)
            pdf_m = re.search(r'href="(/sites/default/files/archivos-anuncios/[^"]+)"', block)
            if not title_m:
                continue
            title = _clean_title(title_m.group(1))
            if not title or len(title) < 12:
                continue
            pdf_url = self._abs_url(pdf_m.group(1)) if pdf_m else TABLON_URL
            fecha = _fecha_from_datetime_attr(dt_m.group(1) if dt_m else "") or _fecha_from_blob(block)
            rows.append(
                {
                    "titulo": title,
                    "fecha": fecha,
                    "url": pdf_url,
                    "source_kind": "tablon",
                }
            )
        return rows

    def _collect_tablon(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        seen: set[str] = set()
        max_page = 0

        try:
            first_html = self._fetch(f"{TABLON_URL}?page=0")
        except urllib.error.URLError:
            return proyectos, licencias

        pages = [int(x) for x in RE_TABLON_PAGER_LAST.findall(first_html)]
        if pages:
            max_page = min(max(pages), self.max_tablon_pages)

        for page in range(0, max_page + 1):
            page_url = f"{TABLON_URL}?page={page}"
            try:
                html = first_html if page == 0 else self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for item in self._parse_tablon_cards(html):
                title = item["titulo"]
                url = item["url"]
                if url in seen:
                    continue
                seen.add(url)
                if RE_TABLON_SKIP.search(title):
                    continue
                if RE_LICENCIA.search(title):
                    licencias.append(
                        {
                            "id": _stable_id("lic", url),
                            "fecha_concesion": None,
                            "fecha_publicacion": item.get("fecha"),
                            "tipo": "licencia / comunicación (tablón)",
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": title,
                            "url": url,
                            "source": "ayuntamiento",
                        }
                    )
                urban_context = re.search(
                    r"urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|"
                    r"reparcel|estudio de detalle|viviendas?|suelo|sector [A-Z0-9-]+",
                    title, re.I,
                )
                if RE_PROYECTO.search(title) and urban_context:
                    rec: dict[str, Any] = {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": title,
                        "fecha": item.get("fecha"),
                        "tipo": _proyecto_tipo(title),
                        "url": url,
                        "source": "ayuntamiento",
                    }
                    proyectos.append(self._enrich_geometry(rec))
        return proyectos, licencias

    def _parse_ultimas_div(self, inner: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for m in re.finditer(r"<b>([^<:]+):</b>\s*([^<]+)", inner):
            fields[m.group(1).strip().lower()] = unescape(m.group(2)).strip()
        doc_m = re.search(r"href='([^']+)'[^>]*>Acceso directo a los documentos", inner)
        pg_m = re.search(r"href='([^']+)'[^>]*>Acceso directo al proyecto", inner)
        if doc_m:
            fields["doc_url"] = doc_m.group(1)
        if pg_m:
            fields["doc_url"] = pg_m.group(1)
        return fields

    def _collect_infourb_ultimas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(ULTIMAS_URL)
        except urllib.error.URLError:
            return rows

        seen: set[str] = set()
        for inner in re.findall(r'<div id="MainContent_myDIV\d+" class="mitipodiv">(.*?)</div>', html, re.S):
            fields = self._parse_ultimas_div(inner)
            figura = fields.get("figura") or fields.get("modificación pg") or ""
            exp = fields.get("expediente") or ""
            desc = fields.get("descripción") or fields.get("descripcion") or ""
            fecha = _parse_fecha_dmy(fields.get("fecha de publicación", "") or fields.get("fecha de publicacion", ""))
            titulo = _clean_title(figura or desc)
            if not titulo:
                continue
            doc_href = fields.get("doc_url") or ULTIMAS_URL
            url = urljoin(INFOURB_BASE + "/", doc_href.lstrip("/"))
            key = f"{exp}|{titulo}"
            if key in seen:
                continue
            seen.add(key)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{titulo} {desc} {fields.get('tipo publicación', '')}"),
                "url": url,
                "source": "ayuntamiento",
                "expediente": exp,
                "origen": "infourb_ultimas",
            }
            rows.append(self._enrich_geometry(rec))
        return rows

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        # Los formularios de solicitud no acreditan una concesión.
        return []

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tablon_proy, _ = self._collect_tablon()
        for rec in tablon_proy:
            add(rec)
        for rec in self._collect_infourb_ultimas():
            add(rec)
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        _, tablon_lic = self._collect_tablon()
        for rec in tablon_lic:
            add(rec)
        for rec in self._collect_licencias_tramites():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
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
        return {"rows": len(rows), "status": "ok"}

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
