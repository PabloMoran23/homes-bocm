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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
DIPALME_WFS = "https://app.dipalme.org/geoserver/urbanismo/ows"
WFS_LAYER = "urbanismo:v_siu_ambitos_o_sectores"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|licencias de ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normas urban|edificaci[oó]n|sancionador|denuncia|"
    r"unidad de ejecuci[oó]n|\bue[\.\-\s]*\d+)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padr[oó]n|subvenci[oó]n|presupuest|feria|jurado|patinete|"
    r"modificaciones presupuestarias|centro de d[ií]a)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://[^/]+\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_ORDENANZA_LINK = re.compile(
    r'<a href="(https://www\.vera\.es/descargar\.php\?[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_ORDENANZA_URBAN = re.compile(
    r"(?i)(normas urban|pgou|planeamiento|edificaci[oó]n|suelo|"
    r"protecci[oó]n del espacio urbano|habitabilidad|licencia urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector|ue|s[\-\s]*\d+|unidad de ejecuci[oó]n)\s*([A-Z0-9\-\.\s]+)\b",
)


@dataclass
class TownConfig:
    id_prefix: str
    municipio: str
    ine: str
    web_base: str
    sede_base: str
    board_url: str | None = None
    seed_pages: list[str] = field(default_factory=list)
    centroid: tuple[float, float] = (0.0, 0.0)


TOWNS: list[TownConfig] = [
    TownConfig(
        id_prefix="ltv",
        municipio="Las Tres Villas",
        ine="04045",
        web_base="https://www.lastresvillas.es",
        sede_base="https://lastresvillas.sedelectronica.es",
        board_url="https://lastresvillas.sedelectronica.es/board/",
        seed_pages=[],
        centroid=(37.1967, -2.7833),
    ),
    TownConfig(
        id_prefix="macael",
        municipio="Macael",
        ine="04061",
        web_base="https://www.macael.es",
        sede_base="https://macael.sedelectronica.es",
        board_url="https://macael.sedelectronica.es/board/",
        centroid=(37.3136, -2.3058),
    ),
    TownConfig(
        id_prefix="cuevas",
        municipio="Cuevas del Almanzora",
        ine="04049",
        web_base="https://www.cuevasdelalmanzora.es",
        sede_base="https://sede.cuevasdelalmanzora.es",
        seed_pages=[
            "https://www.cuevasdelalmanzora.es/ayuntamiento",
        ],
        centroid=(37.2667, -1.8833),
    ),
    TownConfig(
        id_prefix="vera",
        municipio="Vera",
        ine="04102",
        web_base="https://www.vera.es",
        sede_base="https://vera.sedelectronica.es",
        board_url="https://vera.sedelectronica.es/board/",
        seed_pages=[
            "https://www.vera.es/ayuntamiento/index.php?page=ordenanzas",
        ],
        centroid=(37.2469, -1.8690),
    ),
]


def _stable_id(prefix: str, kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip().upper()


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
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
    if "normas urban" in b or "pgou" in b:
        return "normativa urbanística"
    if "ordenanza" in b and "edificaci" in b:
        return "ordenanza de edificación"
    if "plan parcial" in b or ("modificaci" in b and "puntual" in b):
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "sector" in b or re.search(r"\bs[\-\s]*\d+", b):
        return "sector urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class LasTresVillasMacaelCuevasDelAlmanzoraYVeraAyuntamientoAdapter(AyuntamientoAdapter):
    """Cola compuesta Andalucía/Almería: 4 municipios espublico + Diputación WFS sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TOWNS[0].web_base)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sectors_by_ine: dict[str, list[dict[str, Any]]] = {}
        self._sector_index: dict[str, dict[str, dict[str, Any]]] = {}

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ltv-mcv/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ltv-mcv/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _wfs_sectors_url(self, ine: str) -> str:
        cql = urllib.parse.quote(f"cod_ine='{ine}'")
        return (
            f"{DIPALME_WFS}?service=WFS&version=2.0.0&request=GetFeature&"
            f"typeName={WFS_LAYER}&CQL_FILTER={cql}&"
            "outputFormat=application/json&srsName=EPSG:4326"
        )

    def _load_sectors(self, town: TownConfig) -> list[dict[str, Any]]:
        if town.ine in self._sectors_by_ine:
            return self._sectors_by_ine[town.ine]
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(self._wfs_sectors_url(town.ine))
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
                        "uso_dominante": props.get("uso_dominante"),
                        "query_url": self._wfs_sectors_url(town.ine),
                    }
                )
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sectors_by_ine[town.ine] = rows
        index: dict[str, dict[str, Any]] = {}
        for rec in rows:
            index[rec["sector_norm"]] = rec
            short = re.sub(r"[^A-Z0-9]", "", rec["sector_norm"])
            if short:
                index[short] = rec
        self._sector_index[town.ine] = index
        return rows

    def _match_sector(self, town: TownConfig, text: str) -> dict[str, Any] | None:
        if town.ine not in self._sector_index:
            self._load_sectors(town)
        index = self._sector_index.get(town.ine, {})
        title_norm = _norm_text(text)
        for key, rec in index.items():
            if len(key) >= 3 and key in title_norm:
                return rec
        m = RE_SECTOR_CODE.search(text or "")
        if m:
            code = _norm_text(m.group(1))
            if code in index:
                return index[code]
            for key, rec in index.items():
                if code in key or key in code:
                    return rec
        return None

    def _ensure_coords(self, town: TownConfig, rec: dict[str, Any]) -> None:
        if rec.get("lat") is not None and rec.get("lon") is not None:
            return
        rec["lat"] = town.centroid[0]
        rec["lon"] = town.centroid[1]
        rec.setdefault("coord_source", "municipio_centroid")

    def _attach_geometry(self, town: TownConfig, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        match = self._match_sector(town, rec.get("titulo") or "")
        if not match or not match.get("geom"):
            self._ensure_coords(town, rec)
            return
        geom = match["geom"]
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "dipalme_wfs_sector"
        rec["geometry_source_url"] = match.get("query_url")
        rec["coord_source"] = "portal_geometry_centroid"
        rec["sector_urbanistico"] = match.get("sector")
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_espublico_board(self, town: TownConfig) -> list[dict[str, Any]]:
        if not town.board_url:
            return []
        try:
            html = self._fetch(town.board_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento", "Document"):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else town.board_url
            if url.startswith("/"):
                url = f"{town.sede_base}{url}"

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

    def _collect_seed_docs(self, town: TownConfig) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        if town.municipio == "Vera":
            try:
                html = self._fetch(town.seed_pages[0])
            except (urllib.error.URLError, TimeoutError, OSError, IndexError):
                html = ""
            for m in RE_ORDENANZA_LINK.finditer(html):
                url = m.group(1)
                title = _strip_html(m.group(2))
                if not title or url in seen:
                    continue
                if not RE_ORDENANZA_URBAN.search(title):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(title),
                        "url": url,
                        "blob": title,
                        "origen": "ordenanzas",
                    }
                )
            return rows

        for page_url in town.seed_pages:
            try:
                html = self._fetch(page_url, timeout=15)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{4,120})</a>', html, re.I):
                href, title = m.group(1), _strip_html(m.group(2))
                if not RE_PROYECTO.search(f"{title} {href}") and "tablon" not in href.lower():
                    continue
                if href.startswith("/"):
                    doc_url = urllib.parse.urljoin(town.web_base, href)
                elif href.startswith("http"):
                    doc_url = href
                else:
                    continue
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": None,
                        "url": doc_url,
                        "blob": f"{title} {page_url}",
                        "origen": "web_seed",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self, town: TownConfig) -> list[dict[str, Any]]:
        board = town.board_url or (
            town.seed_pages[0]
            if town.seed_pages and "tablon" in town.seed_pages[0].lower()
            else f"{town.sede_base}/board/"
        )
        return [
            {
                "id": _stable_id(town.id_prefix, "lic", board),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": town.centroid[0],
                "lon": town.centroid[1],
                "titulo": f"Tablón de anuncios — {town.municipio}",
                "url": board,
                "source": "ayuntamiento",
                "municipio": town.municipio,
                "nota": "Concesiones y edictos publicados en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id(town.id_prefix, "lic", f"{town.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": town.centroid[0],
                "lon": town.centroid[1],
                "titulo": f"Catálogo de trámites — {town.municipio}",
                "url": f"{town.sede_base}/dossier",
                "source": "ayuntamiento",
                "municipio": town.municipio,
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id(town.id_prefix, "lic", SITUA_SEARCH),
                "fecha_concesion": None,
                "tipo": "consulta planeamiento SITUA",
                "distrito": None,
                "lat": town.centroid[0],
                "lon": town.centroid[1],
                "titulo": f"PGOU {town.municipio} — consulta SITUA (Junta de Andalucía)",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "municipio": town.municipio,
                "nota": "Planeamiento general aprobado en SITUA/Difusión",
                "origen": "situa",
            },
        ]

    def _is_urban_blob(self, blob: str, procedimiento: str = "") -> bool:
        if RE_BOARD_NON_URBAN.search(blob):
            if not re.search(
                r"(?i)(pgou|planeam|urban|licencia|obra|sector|suelo|informaci[oó]n p[uú]blica|ordenanza)",
                blob,
            ):
                return False
        proc = (procedimiento or "").lower()
        if any(
            k in proc
            for k in (
                "planeamiento",
                "licencia",
                "urban",
                "actividad",
                "obra",
                "disposiciones normativas",
                "información pública",
            )
        ):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob, row.get("procedimiento") or ""):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "ocupaci" in proc:
            tipo = "licencia de ocupación"
        elif "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id(town.id_prefix, "lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": town.centroid[0],
            "lon": town.centroid[1],
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "municipio": town.municipio,
            "origen": "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _board_to_proyecto(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob, row.get("procedimiento") or ""):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and not any(
            k in proc for k in ("disposiciones normativas", "planeamiento", "información pública")
        ):
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id(town.id_prefix, "proy", key),
            "municipio": town.municipio,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._attach_geometry(town, rec)
        return rec

    def _sector_to_proyecto(self, town: TownConfig, item: dict[str, Any]) -> dict[str, Any]:
        sector = item["sector"]
        titulo = f"Sector urbanístico {sector} — {town.municipio}"
        if item.get("clase_suelo"):
            titulo = f"{titulo} ({item['clase_suelo']})"
        rec: dict[str, Any] = {
            "id": _stable_id(town.id_prefix, "proy", f"wfs:{town.ine}:{sector}"),
            "municipio": town.municipio,
            "titulo": titulo[:500],
            "fecha": None,
            "tipo": "sector urbanístico",
            "url": f"https://app.dipalme.org/visor-gis/",
            "source": "ayuntamiento",
            "origen": "dipalme_wfs",
            "sector": sector,
            "clase_suelo": item.get("clase_suelo"),
        }
        geom = item.get("geom")
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "dipalme_wfs_sector"
            rec["geometry_source_url"] = item.get("query_url")
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        else:
            self._ensure_coords(town, rec)
        return rec

    def _seed_to_proyecto(self, town: TownConfig, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("origen") != "ordenanzas" and not RE_PROYECTO.search(blob):
            return None
        rec = {
            "id": _stable_id(town.id_prefix, "proy", row["url"]),
            "municipio": town.municipio,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_seed",
        }
        self._attach_geometry(town, rec)
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for town in TOWNS:
            for rec in self._collect_licencia_info_pages(town):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
            for item in self._collect_espublico_board(town):
                rec = self._board_to_licencia(town, item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "situa")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        for r in self._load_jsonl(out_jsonl):
            existing[r["id"]] = r
        merged = list(existing.values())
        self._write_jsonl(out_jsonl, merged)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(merged),
                    "added": max(0, len(merged) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(merged), "added": max(0, len(merged) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for town in TOWNS:
            for item in self._load_sectors(town):
                add(self._sector_to_proyecto(town, item))
            for item in self._collect_seed_docs(town):
                add(self._seed_to_proyecto(town, item))
            for item in self._collect_espublico_board(town):
                add(self._board_to_proyecto(town, item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "dipalme_wfs": sum(1 for r in rows if r.get("origen") == "dipalme_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "ordenanzas"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
