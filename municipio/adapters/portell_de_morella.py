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

WEB_BASE = "https://www.portelldemorella.es"
SEDE_BASE = "https://portelldemorella.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
GVA_PLANEAMIENTO_URL = (
    "https://mediambient.gva.es/es/auto/urbanismo/reg-planeamiento/"
    "3%20CASTELL%C3%93N/12091%20PORTELL%20DE%20MORELLA/"
)
MUNICIPIO = "Portell de Morella"
ID_PREFIX = "portell-de-morella"
INE_MUNICIPIO = "12091"

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"

DEFAULT_NOTICIAS_LIST_URLS: list[str] = [
    f"{WEB_BASE}/es/noticias-0",
    f"{WEB_BASE}/es/noticias-1",
]

DEFAULT_TRANSPARENCY_FOLDERS: list[dict[str, str]] = [
    {
        "titulo": "7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE",
        "url": TRANSPARENCY_URL,
        "nota": "9 documentos en portal transparencia (carga AJAX Wicket)",
    },
]

KNOWN_PGOU: dict[str, str] = {
    "titulo": "PGOU — Texto Refundido (aprobación provisional)",
    "fecha": "2013-01-01",
    "url": "https://www.aug-arquitectos.com/es/el-ayuntamiento-de-portell-de-morella-aprueba-provisionalmente-el-plan-general-de-ordenacion-urbana/",
    "nota": "Aprobación provisional TRV PGOU y Memoria Ambiental (AUG-Arquitectos, 2013)",
}

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|lavadero|mejora(?:s)? urban|obra(?:s)? p[uú]blica|"
    r"acera|entorno urbano|rehabilitaci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"censo electoral|padron|bolsa de|empleo p[uú]blico|subvenci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://portelldemorella\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_NOTICIA_LINK = re.compile(
    r'href="(/es/noticias/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_TITLE_TAG = re.compile(r"<title>([^<|]+)", re.I)

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b:
        return "plan parcial"
    if "lavadero" in b or "obra pública" in b or "mejora urban" in b:
        return "obra pública"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _gml_poslist_to_geojson(poslist: str) -> dict[str, Any] | None:
    coords: list[list[float]] = []
    parts = (poslist or "").split()
    if len(parts) < 6:
        return None
    for i in range(0, len(parts) - 1, 2):
        try:
            lat = float(parts[i])
            lon = float(parts[i + 1])
        except ValueError:
            continue
        coords.append([lon, lat])
    if len(coords) < 4:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _parse_gml_feature(member: ET.Element) -> dict[str, Any] | None:
    feat = member[0]
    props: dict[str, str | None] = {}
    geom: dict[str, Any] | None = None
    for child in feat:
        tag = child.tag.split("}")[-1]
        if tag == "msGeometry":
            pos = child.find(".//gml:posList", GML_NS)
            if pos is not None and pos.text:
                geom = _gml_poslist_to_geojson(pos.text)
            continue
        if tag == "boundedBy":
            continue
        props[tag] = (child.text or "").strip() or None
    if props.get("cod_ine_mun") != INE_MUNICIPIO:
        return None
    return {"props": props, "geom": geom}


class PortellDeMorellaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 9 portalesmunicipales + sede espublico gestiona (sin geometría ICV)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.noticias_list_urls = [
            str(u) for u in (self.config.get("noticias_list_urls") or DEFAULT_NOTICIAS_LIST_URLS)
        ]
        self.transparency_folders: list[dict[str, str]] = list(
            self.config.get("transparency_folders") or DEFAULT_TRANSPARENCY_FOLDERS
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_municipio = str(geom_cfg.get("ine_municipio") or INE_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-portell-de-morella/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-portell-de-morella/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = 0
        while start < 10_000:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.wfs_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "200",
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.wfs_base}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", GML_NS)
            if not members:
                break
            for member in members:
                parsed = _parse_gml_feature(member)
                if parsed:
                    rows.append(parsed)
            start += len(members)
            if len(members) < 200:
                break

        self._wfs_cache = rows
        return rows

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._load_wfs_ambitos():
            props = item["props"]
            geom = item.get("geom")
            pp = props.get("pp") or ""
            ue = props.get("ue") or ""
            clas = props.get("clasificacion") or ""
            titulo = f"{clas} {pp}".strip()
            if ue and ue not in titulo:
                titulo = f"{titulo} — {ue}".strip(" —")
            fecha = props.get("f_aprob") or props.get("f_public")
            key = f"wfs:{props.get('id')}:{pp}:{ue}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(f"{pp} {ue} {clas}"),
                "url": "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz",
                "source": "ayuntamiento",
                "origen": "icv_wfs",
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = (
                    f"{self.wfs_base}?service=WFS&request=GetFeature&typeNames={self.wfs_type}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

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

    def _collect_noticia_links(self) -> list[str]:
        links: set[str] = set()
        for list_url in self.noticias_list_urls:
            try:
                html = self._fetch(list_url)
            except urllib.error.URLError:
                continue
            for m in RE_NOTICIA_LINK.finditer(html):
                links.add(self._abs_web(m.group(1)))
        return sorted(links)

    def _parse_noticia(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        h1_m = RE_H1.search(html)
        title_m = RE_TITLE_TAG.search(html)
        titulo = _strip_html(h1_m.group(1)) if h1_m else ""
        if not titulo and title_m:
            titulo = title_m.group(1).split("|")[0].strip()
        if not titulo:
            return None

        fecha = _fecha_from_blob(html) or _fecha_from_blob(titulo)
        blob = f"{titulo} {_strip_html(html)[:4000]}"
        return {
            "titulo": titulo[:500],
            "fecha": fecha,
            "url": url,
            "blob": blob,
            "origen": "drupal_noticia",
        }

    def _collect_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._collect_noticia_links():
            rec = self._parse_noticia(url)
            if not rec:
                continue
            if RE_BOARD_NON_URBAN.search(rec["blob"]) and not RE_PROYECTO.search(rec["blob"]):
                continue
            if not RE_PROYECTO.search(rec["blob"]) and not RE_LICENCIA.search(rec["blob"]):
                continue
            rows.append(rec)
        return rows

    def _collect_transparency_folders(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for folder in self.transparency_folders:
            titulo = str(folder.get("titulo") or "").strip()
            url = str(folder.get("url") or TRANSPARENCY_URL).strip()
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "procedimiento": "planeamiento urbanístico",
                    "blob": f"{titulo} {folder.get('nota', '')}",
                    "origen": "transparencia",
                }
            )
        return rows

    def _collect_known_pgou(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", "pgou-provisional-2013"),
            "municipio": MUNICIPIO,
            "titulo": KNOWN_PGOU["titulo"],
            "fecha": KNOWN_PGOU["fecha"],
            "tipo": "PGOU",
            "url": KNOWN_PGOU["url"],
            "source": "ayuntamiento",
            "origen": "pgou_conocido",
            "nota": KNOWN_PGOU["nota"],
        }

    def _collect_gva_registro(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", GVA_PLANEAMIENTO_URL),
            "municipio": MUNICIPIO,
            "titulo": "Registro autonómico de planeamiento — Portell de Morella (INE 12091)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": GVA_PLANEAMIENTO_URL,
            "source": "ayuntamiento",
            "origen": "gva_registro",
        }

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
                "nota": "Concesiones y edictos publicados en sede espublico",
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
                "nota": "Licencias, DR y comunicaciones previas vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; sin listado histórico público",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
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
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
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

    def _noticia_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_LICENCIA.search(row["blob"]) and not RE_PROYECTO.search(row["blob"]):
            return None
        if not RE_PROYECTO.search(row["blob"]):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row.get("blob") or row["titulo"]):
            return None
        return {
            "id": _stable_id("proy", row["url"] + row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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

        for rec in self._collect_wfs_proyectos():
            add(rec)
        add(self._collect_known_pgou())
        add(self._collect_gva_registro())
        for item in self._collect_noticias():
            add(self._noticia_to_proyecto(item))
        for item in self._collect_transparency_folders():
            add(self._transparency_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal_noticia": sum(1 for r in rows if r.get("origen") == "drupal_noticia"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        added = result["rows"] - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {**result, "added": max(0, added)}
