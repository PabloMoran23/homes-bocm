from __future__ import annotations

import hashlib
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

WEB_BASE = "https://www.pulpi.es"
TABLON_URL = f"{WEB_BASE}/Servicios/cmsdipro/index.nsf/tablon_view_entidad.xsp?p=Pulpi"
PGOU_DOC_URL = (
    f"{WEB_BASE}/Servicios/cmsdipro/index.nsf/tablon.xsp?"
    "p=Pulpi&documentId=6F1FD9086E6B4226C12582880033ECE5"
)
PGOU_CATEGORY_URL = (
    f"{WEB_BASE}/Servicios/cmsdipro/index.nsf/"
    "tablon_view_entidad_rol_categoria123.xsp?"
    "cat1=Normas&cat2=Planeamiento+Urban%C3%ADstico&cat3=PGOU+PULPI&p=Pulpi"
)
OV_BASE = "https://ov.dipalme.org"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
GEOPORTAL_URL = "https://app.dipalme.org/visor-gis/"
MUNICIPIO = "Pulpí"
ID_PREFIX = "pulpi"
COD_INE = "04075"

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
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de viabilidad)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|ordenanza|normativa urban|evaluaci[oó]n ambiental|vivienda protegida|"
    r"delimitaci[oó]n|reparcel|urbanizaci[oó]n|calificaci[oó]n ambiental)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|oferta empleo|programa activa|concurso-oposici|"
    r"fiestas locales|acta de (?:pleno|junta)|empleo p[uú]blico|subvenci[oó]n|"
    r"estrategia de desarrollo local|gimnasio municipal|consejo local de la infancia)",
)
RE_TABLON_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DOC_ID = re.compile(r"documentId=([A-F0-9]+)", re.I)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector\s+)?((?:s|ue)[\-\s]?)?(ag|rtu|lf|pul|alm|bv|ca|cja|co|ct|ja|nor|par|pc|ph|sal)\s*[\-\s]?(\d+[a-z]?)\b"
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", t.upper()).strip()


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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and "puntual" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class PulpiAyuntamientoAdapter(AyuntamientoAdapter):
    """IBM Domino cmsdipro (pulpi.es tablón + PGOU PDFs) + WFS Diputación Almería sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_doc_url = str(self.config.get("pgou_doc_url") or PGOU_DOC_URL)
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pulpi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "latin-1"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pulpi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_web(self, href: str, page_url: str | None = None) -> str:
        return urljoin(page_url or f"{self.web_base}/", unescape(href))

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
        wfs_url = str(self.config.get("wfs_sectors_url") or WFS_SECTORS_URL)
        try:
            data = self._fetch_json(wfs_url)
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
                        "cod_ine": props.get("cod_ine"),
                        "clase_suelo": props.get("clase_suelo"),
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _sector_codes_from_title(self, title: str) -> list[str]:
        codes: list[str] = []
        for m in RE_SECTOR_CODE.finditer(title or ""):
            prefix = (m.group(1) or "S").upper().replace("-", "").replace(" ", "")
            zone = m.group(2).upper()
            num = m.group(3).upper()
            codes.append(f"{prefix} {zone} {num}".replace("  ", " "))
            codes.append(f"S {zone} {num}")
            codes.append(f"UE {zone} {num}")
        return codes

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        title_codes = {_norm_text(c) for c in self._sector_codes_from_title(title)}
        result: dict[str, Any] | None = None
        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            if len(sector_norm) < 3:
                continue
            compact = sector_norm.replace(" ", "")
            title_compact = title_norm.replace(" ", "")
            if (
                sector_norm in title_norm
                or compact in title_compact
                or sector_norm in title_codes
                or re.search(rf"\b{re.escape(sector_norm)}\b", title_norm)
            ):
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

    def _parse_tablon_rows(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ROW.finditer(html):
            row_html = m.group(1)
            doc_m = RE_DOC_ID.search(row_html)
            if not doc_m:
                continue
            doc_id = doc_m.group(1)
            if doc_id in seen:
                continue
            seen.add(doc_id)

            href_m = re.search(
                rf'href="([^"]*documentId={doc_id}[^"]*)"',
                row_html,
                re.I,
            )
            rel_href = href_m.group(1) if href_m else f"/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Pulpi&documentId={doc_id}"
            url = self._abs_web(rel_href)

            text = _strip_html(row_html)
            if not text or len(text) < 12:
                continue

            title = text.split("Ayuntamiento de Pulp")[0].strip(" -")
            if not title:
                title = text[:300]

            rows.append(
                {
                    "document_id": doc_id,
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(text),
                    "url": url,
                    "blob": text[:2000],
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        return self._parse_tablon_rows(html)

    def _collect_pgou(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, fecha: str | None = None, origen: str = "pgou") -> None:
            if url in seen:
                return
            seen.add(url)
            rec: dict[str, Any] = {
                "url": url,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "blob": f"{titulo} PGOU Pulpí planeamiento",
                "origen": origen,
            }
            rows.append(rec)

        add(self.pgou_doc_url, "Plan General de Ordenación Urbanística (PGOU) de Pulpí", "2018-05-09")
        add(PGOU_CATEGORY_URL, "Tablón — Normas / Planeamiento Urbanístico / PGOU PULPI")
        add(GEOPORTAL_URL, "Visor GIS urbanismo — Diputación de Almería", origen="geoportal")
        add(SITUA_SEARCH, "Consulta planeamiento — SITUADIFusión Junta de Andalucía", origen="situa")

        try:
            html = self._fetch(self.pgou_doc_url)
        except urllib.error.URLError:
            return rows

        pub = _parse_fecha_dmy(html)
        for href in RE_PDF.findall(html):
            pdf_url = self._abs_web(href, self.pgou_doc_url)
            name = urllib.parse.unquote(Path(pdf_url).name.replace("%20", " "))
            if not name.lower().endswith(".pdf"):
                continue
            titulo = f"PGOU Pulpí — {name.rsplit('.', 1)[0]}"
            add(pdf_url, titulo, pub or "2018-05-09", origen="pgou_pdf")

        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_TABLON_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("document_id") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        return self._enrich_geometry(rec)

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        return self._enrich_geometry(rec)

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_TABLON_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("document_id") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites = [
            (
                f"{self.web_base}/Servicios/cmsdipro/index.nsf/servicios.xsp?"
                "documentId=68D12EEAF6BC79DAC1258332002A30CD&p=SedePulpi",
                "Licencia urbanística de obra mayor",
                "licencia de obra mayor",
            ),
            (
                f"{self.web_base}/Servicios/cmsdipro/index.nsf/servicios.xsp?"
                "documentId=6362A33C754472D5C1258332002A32D8&p=Pulpi",
                "Solicitud calificación ambiental",
                "calificación ambiental",
            ),
            (
                f"{OV_BASE}/TiProceeding/ciudadano?entrada=ciudadano&idEntidad=4075"
                "&idExpediente=800210_SolicitudGeneral&idLogica=accesoDirecto",
                "Oficina virtual — presentación telemática (Cl@ve)",
                "oficina virtual",
            ),
            (
                f"{self.web_base}/Servicios/Organizacion/servicios.nsf/"
                "serviciosygrupo.xsp?entidad=Ayuntamiento+de+Pulpi",
                "Guía de servicios y trámites — urbanismo",
                "catálogo trámites",
            ),
        ]
        pages: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede web municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y resoluciones publicados en cmsdipro (Domino)",
                "origen": "tablon",
            }
        ]
        for url, titulo, tipo in tramites:
            pages.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo; concesiones vía oficina virtual DipAlmería",
                    "origen": "web_tramite",
                }
            )
        return pages

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_pgou():
            add(self._doc_to_proyecto(item))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") != "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith("pgou")),
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
