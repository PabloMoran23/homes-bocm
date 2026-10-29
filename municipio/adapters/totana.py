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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.totana.es"
SEDE_BASE = "https://totana.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
RSS_URBANISMO = f"{WEB_BASE}/noticiasrss.asp?area=1"
MUNICIPIO = "Totana"
ID_PREFIX = "totana"
COD_INE = "30039"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    f"&CQL_FILTER=Municipio%3D%27{MUNICIPIO}%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia de actividad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normativa urban|evaluaci[oó]n ambiental|"
    r"delimitaci[oó]n|urbanizaci[oó]n|obras p[uú]blicas|planeamiento|"
    r"desarrollo urban|vivienda|saneamiento|cooperaci[oó]n.*obras)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"pleno|junta de gobierno|elecciones|subvenci[oó]n|bono cheque|"
    r"mesa electoral|jurado|empleo p[uú]blico|bolsa de trabajo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://totana\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_AMBITO = re.compile(r"(?i)\b(UA-\d{1,3}|SECTOR\s+\d+[-\s]?[A-Z]?)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "plan general" in blob or "pgou" in blob or "pgmo" in blob:
        return "PGMO"
    if "plan parcial" in blob:
        return "plan parcial"
    if "obras p" in blob or "cooperaci" in blob:
        return "obras y planeamiento"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class TotanaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web ASP clásica (totana.es) + sede espublico gestiona (tablón/transparencia). WFS CARM sin ámbitos Totana."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.rss_urbanismo = str(self.config.get("rss_urbanismo") or RSS_URBANISMO)
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, latin1: bool = False, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-totana/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
        if latin1:
            return raw.decode("latin-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

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
                cells[cm.group(1)] = _strip_html(cm.group(2))

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
                        f"{descripcion} {titulo}"
                    ),
                }
            )
        return rows

    def _collect_rss_urbanismo(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(self.rss_urbanismo, latin1=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is None or link_el is None:
                continue
            titulo = _strip_html(title_el.text or "")
            url = (link_el.text or "").strip()
            if not titulo or not url:
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url if url.startswith("http") else f"{self.web_base}/{url.lstrip('/')}",
                    "procedimiento": "noticias urbanismo",
                    "blob": titulo,
                    "origen": "rss_urbanismo",
                }
            )
        return rows

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        if "URBANISMO" in html.upper():
            rows.append(
                {
                    "titulo": "Portal transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                    "fecha": None,
                    "url": self.transparency_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": "URBANISMO OBRAS PÚBLICAS MEDIO AMBIENTE transparencia",
                    "origen": "transparencia",
                }
            )

        seen: set[str] = set()
        for m in re.finditer(
            r'href="((?:https://totana\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
            r'[^>]*>([^<]+)',
            html,
            re.I,
        ):
            doc_url = m.group(1)
            if doc_url.startswith("/"):
                doc_url = f"{self.sede_base}{doc_url}"
            if doc_url in seen:
                continue
            seen.add(doc_url)
            doc_title = _strip_html(m.group(2))
            if len(doc_title) < 4 or not RE_PROYECTO.search(doc_title):
                continue
            rows.append(
                {
                    "titulo": doc_title[:500],
                    "fecha": _fecha_from_blob(doc_title),
                    "url": doc_url,
                    "procedimiento": "transparencia urbanismo",
                    "blob": doc_title,
                    "origen": "transparencia",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios en espublico gestiona (/board)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y urbanismo",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Trámites telemáticos; sin histórico público de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado abierto",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Sección con documentación de planeamiento y obras",
                "origen": "transparencia",
            },
        ]

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url, timeout=60))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            ambito = str(props.get("Ambito") or "").strip().upper()
            geom = feat.get("geometry")
            if not ambito or not isinstance(geom, dict):
                continue
            rec = {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[ambito] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "blob", "procedimiento"))
        index = self._build_wfs_index()
        for m in RE_AMBITO.finditer(blob):
            code = m.group(1).upper().replace("SECTOR ", "SECTOR ")
            hit = index.get(code) or index.get(code.replace(" ", "-"))
            if not hit:
                continue
            for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "obra", "servicios p")):
            return True
        if "urbanismo" in cat or "ordenanza" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
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
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_espublico"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_rss_urbanismo():
            add(self._generic_to_proyecto(item))
        for item in self._collect_transparency_index():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss_urbanismo"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
