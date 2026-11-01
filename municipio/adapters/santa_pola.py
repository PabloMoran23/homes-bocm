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

SEDE_BASE = "https://santapola.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
WEB_BASE = "https://santapola.es"
URBANISMO_URL = f"{WEB_BASE}/areas-municipales/urbanismo/"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
REG_PLANEAMIENTO_URL = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/"
    "03122%20SANTA%20POLA/"
)
MUNICIPIO = "Santa Pola"
ID_PREFIX = "santa-pola"
COD_INE_MUN = "03122"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"

ICV_ZONES: list[dict[str, Any]] = [
    {
        "denominaci": "MODIFICACIÓN PUNTUAL N. 8 DEL PLAN GENERAL",
        "expediente": "19950751",
        "tipo": "PGOU",
        "match_tokens": ["modificacion puntual", "plan general", "pgou"],
    },
    {
        "denominaci": "MODIFICACIÓN PUNTUAL N. 21 DEL PLAN GENERAL",
        "expediente": "20041496",
        "tipo": "PGOU",
        "match_tokens": ["modificacion", "plan general", "sector 3", "cj5"],
    },
    {
        "denominaci": "MODIFICACIÓN PUNTUAL N. 23 DEL PLAN GENERAL",
        "expediente": "20050088",
        "tipo": "PGOU",
        "match_tokens": ["modificacion", "plan general", "gran alacant", "poligono 5"],
    },
    {
        "denominaci": "MODIFICACIÓN PUNTUAL Nº 34",
        "expediente": "20210101",
        "tipo": "PGOU",
        "match_tokens": ["modificacion", "plan general", "equipamiento", "deportivo"],
    },
    {
        "denominaci": "HOMOLOGACIÓN Y PLAN PARCIAL SECTOR PP-l/4 EL RODALET",
        "expediente": "20050776",
        "tipo": "plan parcial",
        "match_tokens": ["rodalet", "plan parcial"],
    },
    {
        "denominaci": "PLAN PARCIAL SECTOR I-3 CANASTELL NORTE",
        "expediente": "19950683",
        "tipo": "plan parcial",
        "match_tokens": ["canastell", "i-3", "sector i"],
    },
    {
        "denominaci": "HOMOLOGACIÓN MODIFICATIVA SECTOR I/2 Y PP SECTOR AZORÍN",
        "expediente": "20000743",
        "tipo": "plan parcial",
        "match_tokens": ["azorin", "sector i"],
    },
    {
        "denominaci": "HOMOLOGACIÓN SECTORIAL Y PLAN PARCIAL PP-II/2 EL PILAR",
        "expediente": "20050181",
        "tipo": "plan parcial",
        "match_tokens": ["pilar", "pp-ii"],
    },
    {
        "denominaci": "HOMOLOGACIÓN Y PLAN PARCIAL SECTOR PP-I/1 ALTET",
        "expediente": "20060983",
        "tipo": "plan parcial",
        "match_tokens": ["altet", "pp-i"],
    },
    {
        "denominaci": "HOMOLOGACIÓN Y PLAN PARCIAL SECTOR PP-II/1 TRINQUET",
        "expediente": "20060244",
        "tipo": "plan parcial",
        "match_tokens": ["trinquet"],
    },
    {
        "denominaci": "HOMOLOGACIÓN Y PLAN PARCIAL SECTOR PAU 1 LA ALMAZARA",
        "expediente": "20000904",
        "tipo": "plan parcial",
        "match_tokens": ["almazara", "pau"],
    },
]

URBANISMO_PDFS: list[dict[str, str]] = [
    {
        "titulo": "Registro urbanístico 2025",
        "url": f"{WEB_BASE}/wp-content/uploads/2025/11/Registro-urbanistico-2025.pdf",
        "tipo": "planeamiento",
    },
    {
        "titulo": "Plan de Reforma Interior Barranco Catarra",
        "url": f"{WEB_BASE}/wp-content/uploads/2024/02/Plan-de-Reforma-Interior-Barranco-Catarra.pdf",
        "tipo": "plan parcial",
    },
    {
        "titulo": "Sector 3 CJ5 — PAI (información pública)",
        "url": f"{WEB_BASE}/wp-content/uploads/2025/04/Sector3-CJ5-PAI.pdf",
        "tipo": "información pública",
    },
    {
        "titulo": "Polígono 5.1 Gran Alacant — estudio de detalle",
        "url": f"{WEB_BASE}/wp-content/uploads/2026/07/Poligono-5.1-de-Gran-Alacant-Estudio-de-detalle_Anonimizado.pdf",
        "tipo": "estudio de detalle",
    },
    {
        "titulo": "Parcela equipamiento deportivo — estudio de detalle",
        "url": f"{WEB_BASE}/wp-content/uploads/2025/11/Estudio-de-detalle-sobre-Parcela-de-Equipamiento-Deportivo_Censurado.pdf",
        "tipo": "estudio de detalle",
    },
    {
        "titulo": "Ordenanzas municipales edificación y uso del suelo",
        "url": f"{WEB_BASE}/wp-content/uploads/bsk-pdf-manager/2021/01/Ordenanzas-Municipales-de-la-edificacion-y-uso-del-suelo_BOP_2_5-01-2021.pdf",
        "tipo": "ordenanza",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|segunda ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de integraci[oó]n)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|nnss|pgmod|"
    r"estudio de detalle|gran alacant|registro urban|pai\b|barranco)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|auxiliar administrativo|modificaci[oó]n de cr[eé]ditos|"
    r"cr[eé]ditos n|suplemento de cr[eé]dito|presupuest|subvenci[oó]n|empleo p[uú]blico|"
    r"matrimonio|delegaci[oó]n de funciones)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://santapola\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_LINK = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _fecha_from_expediente(expediente: str) -> str | None:
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 8:
        try:
            y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
            if 1980 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(expediente or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").upper().replace("Ó", "O").replace("É", "E").replace("Í", "I"))


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    shapes = []
    for f in features:
        g = f.get("geometry")
        if isinstance(g, dict) and g.get("type"):
            try:
                shapes.append(shape(g))
            except Exception:
                continue
    if not shapes:
        return None
    merged = unary_union(shapes)
    if merged.is_empty:
        return None
    if not merged.is_valid:
        merged = merged.buffer(0)
    if merged.is_empty or not merged.is_valid:
        return None
    return json.loads(json.dumps(mapping(merged)))


class SantaPolaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress santapola.es + sede espublico gestiona + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.reg_planeamiento_url = str(
            self.config.get("reg_planeamiento_url") or REG_PLANEAMIENTO_URL
        )
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._icv_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santa-pola/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santa-pola/1.0")},
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

    def _fetch_icv_zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        # ICV WFS (cod_ine_mun 03122) no pasa validación h03 vs límite IGN; ver RESEARCH.md.
        return None

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = _normalize_title(titulo)
        best: tuple[float, dict[str, Any]] | None = None
        for zone in ICV_ZONES:
            score = 0.0
            for token in zone.get("match_tokens") or []:
                if token.upper() in norm:
                    score += 25.0
            den = _normalize_title(zone.get("denominaci") or "")
            if den and den in norm:
                score = max(score, 100.0)
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)
        if best and best[0] >= 25:
            return best[1]
        return None

    def _should_enrich_board_geometry(self, rec: dict[str, Any], *, licencia: bool) -> bool:
        titulo = rec.get("titulo") or ""
        if licencia:
            return bool(re.search(r"(?i)pol[ií]gono|parcela|diseminad|sector", titulo))
        return rec.get("tipo") in {"planeamiento", "información pública", "PGOU", "plan parcial"}

    def _enrich_geometry(self, rec: dict[str, Any], *, licencia: bool = False) -> None:
        if record_geometry(rec):
            return
        if rec.get("origen") == "tablon" and not self._should_enrich_board_geometry(rec, licencia=licencia):
            return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._fetch_icv_zone_geometry(zone)
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor_url = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for zone in ICV_ZONES:
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(zone.get("expediente", "")),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._fetch_icv_zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_web_pdf_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        pdfs = list(URBANISMO_PDFS)
        try:
            html = self._fetch(self.urbanismo_url)
            seen_urls = {p["url"] for p in pdfs}
            for m in RE_PDF_LINK.finditer(html):
                href = m.group(1)
                if href.startswith("/"):
                    href = f"{self.web_base}{href}"
                if href in seen_urls or "wp-content/uploads" not in href:
                    continue
                seen_urls.add(href)
                pdfs.append(
                    {
                        "titulo": f"Documento urbanismo — {href.rsplit('/', 1)[-1]}",
                        "url": href,
                        "tipo": "planeamiento",
                    }
                )
        except urllib.error.URLError:
            pass

        for pdf in pdfs:
            titulo = pdf["titulo"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf["url"]),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": "2001-12-25" if "pgou" in titulo.lower() or "normativa" in titulo.lower() else None,
                "tipo": pdf.get("tipo") or "planeamiento",
                "url": pdf["url"],
                "source": "ayuntamiento",
                "origen": "web_pdf",
            }
            self._enrich_geometry(rec, licencia=False)
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y actividades",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos de licencias publicados en sede espublico",
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
                "nota": "Licencias 1ª/2ª ocupación, DR obras reforma",
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

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.urbanismo_url),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo — planes y normativa (web municipal)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web",
            },
            {
                "id": _stable_id("proy", self.transparency_url),
                "municipio": MUNICIPIO,
                "titulo": "Portal transparencia — carpeta urbanismo (sede)",
                "fecha": None,
                "tipo": "transparencia",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
                "nota": "Carpeta LGT 7 — instrumentos planeamiento (Wicket AJAX)",
            },
            {
                "id": _stable_id("proy", self.reg_planeamiento_url),
                "municipio": MUNICIPIO,
                "titulo": "Registro planeamiento GVA — Santa Pola",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.reg_planeamiento_url,
                "source": "ayuntamiento",
                "origen": "gva_registro",
                "nota": "Índice instrumentos PG, planes parciales y modificaciones",
            },
            {
                "id": _stable_id(
                    "proy",
                    "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica",
                ),
                "municipio": MUNICIPIO,
                "titulo": "ICV — zonificación urbanística Comunitat Valenciana",
                "fecha": None,
                "tipo": "visor GIS",
                "url": "https://dadesobertes.gva.es/dataset/planeamiento-urbanistico-de-la-comunitat-valenciana-zonificacion-urbanistica",
                "source": "ayuntamiento",
                "origen": "datos_abiertos",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "licencias" not in (row.get("procedimiento") or "").lower():
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        elif "ocupaci" in blob.lower():
            tipo = "licencia de ocupación"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
        self._enrich_geometry(rec, licencia=True)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower():
                return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento|homologaci[oó]n|sector|plan parcial|pgou", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|dogv", blob):
            tipo = "información pública"

        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec, licencia=False)
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for rec in self._collect_icv_proyectos():
            add(rec)
        for rec in self._collect_web_pdf_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
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
