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

WEB_BASE = "https://www.morella.net"
SEDE_BASE = "https://morella.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Morella"
ID_PREFIX = "morella"
INE_CODE = "12080"

GVA_PGOU_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/"
    "2.%20Textos%20consolidados,%20Orden%2010-2022/12080%20Morella/"
)
ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"

WEB_SEEDS: tuple[tuple[str, str], ...] = (
    ("Normativa urbanística (PGOU)", f"{WEB_BASE}/normativa-urbanistica/?lang=es"),
    ("Oficina de Obras y Servicios", f"{WEB_BASE}/oficina-obres-i-serveis/?lang=es"),
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla especial|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|zonificaci[oó]n|clasificaci[oó]n|ordenaci[oó]n pormenorizada|normas urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|nomenament|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó] fiscal|tasas e impuestos|reglament org|"
    r"compte general|itv|electores|cens electoral)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://morella\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_GVA_PDF = re.compile(r'href="([^"]+\.pdf)"', re.I)
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
    if "normas urban" in blob:
        return "normas urbanísticas PGOU"
    if "zonificaci" in blob:
        return "zonificación PGOU"
    if "clasificaci" in blob:
        return "clasificación del suelo"
    if "ordenaci" in blob and "pormenor" in blob:
        return "ordenación pormenorizada"
    if "plan parcial" in blob or re.search(r"\bpp[\s-]", blob):
        return "plan parcial"
    if "plan especial" in blob or "pla especial" in blob:
        return "plan especial"
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "unidad de actuaci" in blob or re.search(r"\bua[\s-]", blob):
        return "unidad de actuación"
    if "sector" in blob or re.search(r"\bsu[\s-]", blob):
        return "sector / unidad de ejecución"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "licencia" in blob:
        return "licencia publicada"
    return "planeamiento"


def _gml_poslist_to_ring(poslist: str) -> list[list[float]]:
    nums = [float(x) for x in re.split(r"\s+", poslist.strip()) if x]
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    rings: list[list[list[float]]] = []
    for pos in feat.iter():
        if pos.tag.endswith("posList") and pos.text:
            ring = _gml_poslist_to_ring(pos.text)
            if len(ring) >= 4:
                rings.append(ring)
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}


class MorellaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico + textos consolidados PGOU (GVA) + ICV WFS InventarioSuSuz y Zonificación."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.gva_pgou_index = str(self.config.get("gva_pgou_index") or GVA_PGOU_INDEX)
        self.icv_wfs_base = str(self.config.get("icv_wfs_base") or ICV_WFS_BASE).rstrip("/")
        self.ine_code = str(self.config.get("ine_code") or INE_CODE)
        self.web_seeds = tuple(
            (str(t), str(u)) for t, u in (self.config.get("web_seeds") or WEB_SEEDS)
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._inventario_cache: list[dict[str, Any]] | None = None
        self._zonificacion_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-morella/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-morella/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

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

    def _collect_gva_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.gva_pgou_index)
        except urllib.error.URLError:
            return rows
        base = self.gva_pgou_index if self.gva_pgou_index.endswith("/") else f"{self.gva_pgou_index}/"
        for href in RE_GVA_PDF.findall(html):
            if href.startswith("?"):
                continue
            doc_url = urllib.parse.urljoin(base, href)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            name = unescape(urllib.parse.unquote(Path(href).name))
            rows.append(
                {
                    "titulo": f"PGOU Morella — {name}",
                    "fecha": _fecha_from_blob(name),
                    "url": doc_url,
                    "blob": name,
                    "origen": "gva_pgou_pdf",
                }
            )
        return rows

    def _inventario_wfs_url(self, start_index: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "InventarioSuSuz",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "200",
                "STARTINDEX": str(start_index),
            }
        )
        return f"{self.icv_wfs_base}?{params}"

    def _collect_inventario_wfs(self) -> list[dict[str, Any]]:
        if self._inventario_cache is not None:
            return self._inventario_cache

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for start in range(0, 20_000, 200):
            url = self._inventario_wfs_url(start)
            try:
                root = ET.fromstring(self._fetch_bytes(url))
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//{http://www.opengis.net/wfs/2.0}member")
            if not members:
                break
            for mem in members:
                feat = mem[0]
                props: dict[str, str] = {}
                for child in feat:
                    tag = child.tag.split("}")[-1]
                    if tag in ("msGeometry", "boundedBy"):
                        continue
                    txt = (child.text or "").strip()
                    if txt:
                        props[tag] = txt
                if props.get("cod_ine_mun") != self.ine_code:
                    continue
                key = props.get("id") or props.get("pp") or ""
                if key in seen:
                    continue
                seen.add(key)
                pp = props.get("pp") or ""
                ue = props.get("ue") or ""
                clas = props.get("clasificacion") or ""
                titulo = " ".join(p for p in (clas, pp, ue) if p).strip()
                geom = _gml_feature_to_geojson(feat)
                wfs_q = urllib.parse.urlencode(
                    {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": "InventarioSuSuz",
                        "outputFormat": "GML3",
                        "srsName": "EPSG:4326",
                        "count": "1",
                        "CQL_FILTER": f"id='{props.get('id')}'",
                    }
                )
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"inv:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": props.get("f_aprob") or props.get("f_public") or None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": (
                        "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                        f"#municipio={MUNICIPIO}"
                    ),
                    "source": "ayuntamiento",
                    "origen": "icv_inventario_wfs",
                    "sector": pp or None,
                    "ue": ue or None,
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = f"{self.icv_wfs_base}?{wfs_q}"
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            if len(members) < 200:
                break

        self._inventario_cache = rows
        return rows

    def _zonificacion_wfs_url(self, start_index: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "Planeamiento.Zonificacion",
                "outputFormat": "application/gml+xml; version=3.2",
                "count": "100",
                "startIndex": str(start_index),
                "srsName": "EPSG:4326",
            }
        )
        return f"{self.icv_wfs_base}?{params}"

    def _collect_zonificacion_wfs(self) -> list[dict[str, Any]]:
        if self._zonificacion_cache is not None:
            return self._zonificacion_cache

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for start in range(0, 5000, 100):
            url = self._zonificacion_wfs_url(start)
            try:
                root = ET.fromstring(self._fetch_bytes(url))
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//{http://www.opengis.net/wfs/2.0}member")
            if not members:
                break
            for mem in members:
                feat = mem[0]
                props: dict[str, str] = {}
                for child in feat:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        continue
                    txt = "".join(child.itertext()).strip()
                    if txt:
                        props[tag] = txt
                if props.get("cod_ine_mun") != self.ine_code:
                    continue
                key = "|".join(
                    [
                        props.get("expediente", ""),
                        props.get("denominaci", ""),
                        props.get("zon_suelo", ""),
                    ]
                )
                if key in seen:
                    continue
                seen.add(key)
                titulo = props.get("denominaci") or props.get("denominaci_val") or "Zonificación PGOU"
                zona = props.get("zon_suelo") or ""
                if zona:
                    titulo = f"{titulo} — {zona}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"zon:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(props.get("expediente", "")),
                    "tipo": _proyecto_tipo(titulo),
                    "url": props.get("url_abs") or url,
                    "source": "ayuntamiento",
                    "origen": "icv_zonificacion_wfs",
                    "expediente": props.get("expediente") or None,
                    "zon_suelo": zona or None,
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            if len(members) < 100:
                break

        self._zonificacion_cache = rows
        return rows

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": title,
                "fecha": None,
                "url": url,
                "blob": f"{title} planeamiento urbanismo PGOU",
                "origen": "web_seed",
            }
            for title, url in self.web_seeds
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
                "titulo": "Tablón d'anuncis — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catàleg de tràmits — licencias d'obra",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Sin listado histórico público de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", WEB_SEEDS[1][1]),
                "fecha_concesion": None,
                "tipo": "oficina obras y licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Oficina de Obras y Servicios — licencias urbanísticas",
                "url": WEB_SEEDS[1][1],
                "source": "ayuntamiento",
                "nota": "Trámites presenciales; web protegida por Cloudflare en scraping automatizado",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "llicència")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
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
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
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

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _gva_pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_gva_pgou_pdfs():
            add(self._gva_pdf_to_proyecto(item))
        for item in self._collect_web_seeds():
            add(self._seed_to_proyecto(item))
        for item in self._collect_inventario_wfs():
            add(item)
        for item in self._collect_zonificacion_wfs():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "gva_pdf": sum(1 for r in rows if r.get("origen") == "gva_pgou_pdf"),
            "icv_inventario": sum(1 for r in rows if r.get("origen") == "icv_inventario_wfs"),
            "icv_zonificacion": sum(1 for r in rows if r.get("origen") == "icv_zonificacion_wfs"),
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
