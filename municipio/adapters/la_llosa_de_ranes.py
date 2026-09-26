from __future__ import annotations

import hashlib
import json
import re
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

WEB_BASE = "https://www.lallosaderanes.es"
SEDE_BASE = "https://lallosaderanes.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "La Llosa de Ranes"
ID_PREFIX = "la-llosa-de-ranes"
INE_MUNICIPIO = "46157"

WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/pagina/urbanisme",
    f"{WEB_BASE}/pagina/informacio-publica-modificacio-puntual-del-pla-especial-narengs",
    (
        f"{WEB_BASE}/pagina/informacio-publica-versio-preliminar-del-pla-general-"
        "informe-sostenibilitat-ambiental-estudi-preliminar-del-paisatge"
    ),
    f"{WEB_BASE}/pagina/instancies-sollicituds",
    f"{WEB_BASE}/listado-titulares/anuncio",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó] responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|inicio de obra|"
    r"instancia.?obres|compatibilidad urban|ambiental funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"expropi|nareng|sector|ue[\s\-]?\d|unidad de actuaci[oó]n|"
    r"estudi (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|"
    r"aprobaci[oó]n (?:inicial|definitiva)|conveni|urbanitz)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"calendario fiscal|calendari fiscal|subvenci[oó]n|precios p[uú]blicos|"
    r"ordenanza fiscal|convocatoria.*pleno|juez de paz|campanya.*mosquits|"
    r"control de vectors)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://lallosaderanes\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.lallosaderanes\.es)?/sites/www\.lallosaderanes\.es/files/[^"]+\.(?:pdf|PDF))"',
    re.I,
)
RE_AVISO_HREF = re.compile(
    r'href="((?:https://www\.lallosaderanes\.es)?/(?:aviso|pagina)/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector|ue|ua)\s*([A-Z]?\s*\d+|[A-Z])\b",
)

GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


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
    if "nareng" in b or "plan especial" in b:
        return "plan especial"
    if "pla general" in b or "pgou" in b:
        return "plan general"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "expropi" in b:
        return "expropiación"
    if "sector" in b:
        return "sector planeamiento"
    if re.search(r"\bue[\s\-]?\d+", b):
        return "unidad de ejecución"
    return "planeamiento"


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
            polygon = child.find(".//gml:Polygon", GML_NS)
            if polygon is not None:
                pos = polygon.find(".//gml:posList", GML_NS)
                if pos is not None and pos.text:
                    geom = _gml_poslist_to_geojson(pos.text)
            continue
        if tag == "boundedBy":
            continue
        props[tag] = (child.text or "").strip() or None
    if props.get("cod_ine_mun") != INE_MUNICIPIO:
        return None
    return {"props": props, "geom": geom}


class LaLlosaDeRanesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_municipio = str(geom_cfg.get("ine_municipio") or INE_MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-llosa-de-ranes/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-llosa-de-ranes/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_web(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.web_base}/", href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = 0
        while start < 25_000:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.wfs_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "200",
                    "startIndex": str(start),
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

    def _wfs_query_url(self, ambito_id: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "1",
                "CQL_FILTER": f"id='{_sql_escape(ambito_id)}'",
            }
        )
        return f"{self.wfs_base}?{params}"

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
                "url": (
                    "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                    f"#municipio={MUNICIPIO}"
                ),
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "sector": pp,
                "ue": ue,
            }
            if geom:
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = self._wfs_query_url(str(props.get("id") or key))
                rec["coord_source"] = "portal_geometry_centroid"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
            page_title = _strip_html(h1_m.group(1)) if h1_m else page_url

            if RE_PROYECTO.search(page_title) or RE_LICENCIA.search(page_title):
                if page_url not in seen:
                    seen.add(page_url)
                    rows.append(
                        {
                            "titulo": page_title[:500],
                            "fecha": _fecha_from_blob(page_title),
                            "url": page_url,
                            "page_url": page_url,
                            "blob": f"{page_title} {page_url}",
                            "origen": "drupal_pagina",
                        }
                    )

            for m in re.finditer(r'href="(/sites/www\.lallosaderanes\.es/files/[^"]+\.(?:pdf|zip))"', html, re.I):
                href = m.group(1)
                doc_url = self._abs_web(href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                name = unescape(urllib.parse.unquote(Path(href).name))
                titulo = f"{page_title} — {name}"
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(name),
                        "url": doc_url,
                        "page_url": page_url,
                        "blob": f"{titulo} {page_url}",
                        "origen": "drupal_pdf",
                    }
                )

            for m in RE_AVISO_HREF.finditer(html):
                path = m.group(1)
                aviso_url = self._abs_web(path)
                if aviso_url in seen:
                    continue
                slug_part = path.rsplit("/", 1)[-1]
                titulo = slug_part.replace("-", " ")
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                seen.add(aviso_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(slug_part),
                        "url": aviso_url,
                        "page_url": page_url,
                        "blob": f"{titulo} {aviso_url}",
                        "origen": "drupal_aviso",
                    }
                )
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
            url = self._abs_sede(url)

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
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/pagina/instancies-sollicituds"),
                "fecha_concesion": None,
                "tipo": "formularios licencias y obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Instàncies i sol·licituds — licencias de obra",
                "url": f"{self.web_base}/pagina/instancies-sollicituds",
                "source": "ayuntamiento",
                "nota": "Formularios instancia obras, comunicación actividades, licencia ambiental",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
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

    def _match_geometry(self, titulo: str) -> dict[str, Any] | None:
        blob = titulo.upper()
        for item in self._load_wfs_ambitos():
            props = item["props"]
            pp = str(props.get("pp") or "").upper()
            ue = str(props.get("ue") or "").upper()
            if pp and pp in blob:
                return item
            if ue and re.search(rf"\b{re.escape(ue)}\b", blob):
                return item
        m = RE_SECTOR_CODE.search(titulo)
        if m:
            code = re.sub(r"\s+", " ", m.group(1).strip()).upper()
            for item in self._load_wfs_ambitos():
                props = item["props"]
                pp = str(props.get("pp") or "").upper()
                if code in pp or pp.endswith(code):
                    return item
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        match = self._match_geometry(rec.get("titulo") or "")
        if not match:
            return
        geom = match.get("geom")
        if not geom:
            return
        props = match["props"]
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = self._wfs_query_url(str(props.get("id") or ""))
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            if not re.search(
                r"(?i)(pgou|planeam|urban|licencia|obra|sector|suelo|informaci[oó]n p[uú]blica|nareng)",
                blob,
            ):
                return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
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
        if "ambiental" in proc or "ambiental" in blob.lower():
            tipo = "licencia ambiental"
        elif "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        rec = {
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
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec = {
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
        self._attach_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "drupal_pagina",
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
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
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
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if str(r.get("origen") or "").startswith("drupal")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
