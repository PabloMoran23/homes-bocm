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

SEDE_BASE = "https://alfaradelpatriarca.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
WEB_BASE = "https://www.alfaradelpatriarca.es"
URBANISMO_URL = f"{WEB_BASE}/es/pagina/urbanismo"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
MUNICIPIO = "Alfara del Patriarca"
ID_PREFIX = "alfara-del-patriarca"
COD_INE_MUN = "46025"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "ms:Planeamiento.Zonificacion"
ICV_VISOR_URL = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

ICV_ZONES: list[dict[str, Any]] = [
    {
        "expediente": "19981541",
        "denominaci": "Plan general de ordenación urbana (PGOU)",
        "tipo": "PGOU",
        "fids": [
            "18830",
            "54016",
            "54045",
            "63241",
            "4095",
            "4096",
            "4097",
            "4098",
            "4099",
            "4101",
            "4111",
            "4112",
            "18827",
            "18859",
            "18918",
            "18919",
            "18920",
            "18921",
            "31331",
            "31372",
            "31373",
            "31393",
            "31394",
            "31395",
            "31396",
            "31397",
            "31425",
            "46719",
            "46720",
            "48134",
            "48143",
            "48152",
            "48160",
            "49243",
        ],
    },
    {
        "expediente": "20030478",
        "denominaci": "Plan parcial Sector ARR-2",
        "tipo": "plan parcial",
        "fids": ["4094", "4100", "5272"],
    },
    {
        "expediente": "20060272",
        "denominaci": "Plan de Reforma Interior Sector San Diego",
        "tipo": "reforma interior",
        "fids": ["55385"],
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|minimizaci[oó]n de impacto territorial|lmit|estudio de integraci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de integraci[oó]n)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|pol[ií]gono|suelo|sector|"
    r"cambio de uso|normas subsidiarias|homologaci[oó]n|ordenanza|reforma interior|arr-2|san diego)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padr[oó]n|presupuest|subvenci[oó]n|empleo p[uú]blico|"
    r"modificaci[oó]n de cr[eé]ditos|cr[eé]ditos n|cr[eé]ditos extraordinarios|"
    r"transferencias de cr[eé]dito|becas ceu|concurso de poes|concurso de poes[ií]a|"
    r"ivtm|ibi\b|casetones|piscina|sometimiento a ip|liquidaci[oó]n del 20\d\d|"
    r"elevaci[oó]n a definitivo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://alfaradelpatriarca\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.alfaradelpatriarca\.es)?/[^\"]+\.pdf[^\"]*)"',
    re.I,
)
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


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class AlfaraDelPatriarcaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + web municipal (urbanismo) + ICV WFS zonificación (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alfara-del-patriarca/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        return json.loads(self._fetch(url, timeout=timeout))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.sede_base}/", href.lstrip("/"))

    def _abs_web(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.web_base}/", href.lstrip("/"))

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
            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()

            expediente = cells.get("class_expedient") or cells.get("class_expediente") or ""
            procedimiento = cells.get("class_procedure") or cells.get("class_procedimiento") or ""
            categoria = cells.get("class_category") or cells.get("class_categoria") or ""
            descripcion = cells.get("class_description") or ""
            fecha_raw = cells.get("class_date") or cells.get("class_fecha") or ""

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

    def _icv_feature_url(self, fid: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.icv_type_name,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": "1",
                "featureId": f"Planeamiento.Zonificacion.{fid}",
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _fetch_icv_geometry(self, fids: list[str]) -> dict[str, Any] | None:
        cache_key = ",".join(sorted(fids))
        if cache_key in self._icv_geom_cache:
            cached = self._icv_geom_cache[cache_key]
            return dict(cached) if cached else None

        features: list[dict[str, Any]] = []
        sample_url = ""
        for fid in fids:
            url = self._icv_feature_url(fid)
            try:
                data = self._fetch_json(url, timeout=45)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                    continue
                features.append(feat)
                sample_url = url

        merged = _merge_geometries(features)
        if not merged:
            self._icv_geom_cache[cache_key] = None
            return None

        result = {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": sample_url or f"{self.icv_wfs_url}?cod_ine_mun={self.cod_ine_mun}",
            "coord_source": "portal_geometry_centroid",
        }
        self._icv_geom_cache[cache_key] = result
        return dict(result)

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for zone in ICV_ZONES:
            titulo = str(zone["denominaci"])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_expediente(str(zone.get("expediente", ""))),
                "tipo": zone.get("tipo") or "planeamiento",
                "url": ICV_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._fetch_icv_geometry(list(zone.get("fids") or []))
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_web_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.urbanismo_url, timeout=25)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rows

        seen: set[str] = set()
        for href_m in RE_PDF_HREF.finditer(html):
            href = self._abs_web(href_m.group(1))
            if href in seen:
                continue
            seen.add(href)
            titulo = _strip_html(href_m.group(0))
            blob = f"{titulo} {href}"
            if not RE_PROYECTO.search(blob) and "urban" not in blob.lower():
                continue
            rows.append(
                {
                    "id": _stable_id("proy", href),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500] or href.rsplit("/", 1)[-1],
                    "fecha": _fecha_from_expediente(titulo),
                    "tipo": "planeamiento",
                    "url": href,
                    "source": "ayuntamiento",
                    "origen": "web_urbanismo",
                }
            )

        for heading in (
            "Plan general de ordenación urbana",
            "Plan parcial Sector ARR-2",
            "Plan de Reforma Interior Sector San Diego",
        ):
            if heading.lower() in html.lower():
                rows.append(
                    {
                        "id": _stable_id("proy", f"web:{heading}"),
                        "municipio": MUNICIPIO,
                        "titulo": heading,
                        "fecha": _fecha_from_expediente(heading),
                        "tipo": "planeamiento",
                        "url": self.urbanismo_url,
                        "source": "ayuntamiento",
                        "origen": "web_urbanismo",
                    }
                )
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
                "titulo": "Tablón de anuncios — licencias y edictos urbanísticos",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Publicación de licencias y LMIT en sede espublico",
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
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — urbanismo y obras públicas",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Sección 7: instrumentos y documentación urbanística",
                "origen": "transparencia",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", self.urbanismo_url),
                "municipio": MUNICIPIO,
                "titulo": "Instrumentos de planeamiento — web municipal",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
                "nota": "PGOU, plan parcial ARR-2 y reforma interior San Diego",
            },
            {
                "id": _stable_id("proy", self.transparency_url),
                "municipio": MUNICIPIO,
                "titulo": "Urbanismo — portal transparencia sede",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
                "nota": "7 documentos en sección urbanismo/obras/medio ambiente",
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
        if not RE_LICENCIA.search(blob) and "licencias urban" not in (row.get("procedimiento") or "").lower():
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "minimizaci" in blob.lower() or "lmit" in blob.lower():
            tipo = "licencia minimización impacto territorial"
        elif "actividad" in proc:
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
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower():
                return None
        proc = (row.get("procedimiento") or "").lower()
        urban_blob = re.search(
            r"(?i)(planeam|urban|licencia|obra|expedient|sector|pgou|reforma interior|"
            r"plan parcial|informaci[oó]n p[uú]blica|dogv|suelo|parcela|pol[ií]gono)",
            blob,
        )
        if not urban_blob and "planeamiento" not in proc and "normativa" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento|normas subsidiarias|homologaci[oó]n", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|estudio de integraci[oó]n", blob):
            tipo = "información pública"
        elif re.search(r"(?i)ordenanza|reglamento", blob):
            tipo = "normativa"

        key = row.get("expediente") or row["url"]
        return {
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia")),
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
        for rec in self._collect_web_urbanismo():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
