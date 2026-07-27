from __future__ import annotations

import hashlib
import json
import re
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
from municipio.gis.sitcm import resolve_ambito_geometry

WEB_BASE = "http://www.camarmadeesteruelas.es"
SEDE_BASE = "https://camarmadeesteruelas.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
AYUNTAMIENTO_URL = f"{WEB_BASE}/ayuntamiento/"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
MUNICIPIO = "Camarma de Esteruelas"
ID_PREFIX = "camarma-de-esteruelas"
WFS_MUNICIPIO = "CAMARMA DE ESTERUELAS"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|actividad)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"evaluaci[oó]n ambiental.*actividad|documentaci[oó]n licencia|"
    r"ordenanza.*construc|apertura_estable|instalacionanuncios|licencias_autotaxi)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|normas subsidiarias|"
    r"ordenanza|edtu|sector|urbanizaci[oó]n|nnss|plusvalia|dominio p[uú]blico|"
    r"calificaci[oó]n urban|industrial|unidad de ejecuci[oó]n|\bue-\d+)",
)
RE_URBANISMO_PDF = re.compile(
    r"(?i)(urban|planeam|construc|nnss|bocm|serviciosurban|anuncio|licen|obra|"
    r"plusvalia|dominio|apertura_estable|tasas_serv_urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_ ](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DATA_LABEL = re.compile(r'data-label="([^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://camarmadeesteruelas\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href="(/media/\d+/[^"]+\.pdf)"', re.I)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    m = re.search(r"BOCM[- ]?(\d{1,2})[- ](\d{1,2})[- ](\d{4})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "peri" in n or "plan especial" in n:
        return "planeamiento"
    if "bocm" in n:
        return "publicación BOCM"
    if "plusvalia" in n or "plusvalía" in n:
        return "plusvalía municipal"
    if "dominio" in n:
        return "dominio público"
    if "construc" in n:
        return "ordenanza edificación"
    if "serviciosurban" in n or "tasas_serv_urban" in n:
        return "servicios urbanísticos"
    if "instalacionanuncios" in n or "anuncio" in n:
        return "instalación de anuncios"
    if "apertura_estable" in n:
        return "apertura establecimientos"
    if "licencias_autotaxi" in n:
        return "licencias autotaxi"
    if re.search(r"declaraci[oó]n responsable", n):
        return "declaración responsable"
    if "licencia" in n:
        return "modelo licencia"
    return "documento urbanismo"


class CamarmaDeEsteruelasAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Umbraco/Bootstrap (ordenanzas urbanismo) + tablón eHome espublico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.ayuntamiento_url = str(self.config.get("ayuntamiento_url") or AYUNTAMIENTO_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-camarma-de-esteruelas/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str = WEB_BASE) -> str:
        return urllib.parse.urljoin(f"{base}/", href)

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, _meta = resolve_ambito_geometry(WFS_MUNICIPIO, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": "https://idem.comunidad.madrid/geoserver3/ows",
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": _meta.get("ambito_name"),
            }
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells: dict[str, str] = {}
            for label_m in RE_DATA_LABEL.finditer(row_html):
                label = label_m.group(1).strip().lower()
                cells[label] = _strip_html(label_m.group(2))
            if not cells:
                continue
            documento = cells.get("documento", "")
            if documento.lower() == "documento":
                continue

            expediente = cells.get("expediente", "")
            procedimiento = cells.get("procedimiento", "")
            categoria = cells.get("categoría", cells.get("categoria", ""))
            descripcion = cells.get("descripción", cells.get("descripcion", ""))
            fecha_raw = cells.get("fecha de publicación", cells.get("fecha de publicacion", ""))

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
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
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_ordenanzas_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.ayuntamiento_url)
        except urllib.error.URLError:
            return rows

        for m in RE_PDF_HREF.finditer(html):
            href = m.group(1)
            name = unescape(urllib.parse.unquote(Path(href).name))
            if not RE_URBANISMO_PDF.search(name):
                continue
            pdf = self._abs_url(href)
            if pdf in seen:
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                    "url": self.ayuntamiento_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": "ordenanzas_web",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.ayuntamiento_url),
                "fecha_concesion": None,
                "tipo": "ordenanzas urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ayuntamiento — ordenanzas urbanismo y edificación",
                "url": self.ayuntamiento_url,
                "source": "ayuntamiento",
                "nota": "Ordenanzas municipales (urbanismo, construcción, licencias)",
                "origen": "ordenanzas_web",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y resoluciones publicadas",
                "origen": "tablon_sede",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo de trámites",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes urbanísticas",
                "origen": "sede_tramites",
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
                "nota": "Documentación urbanismo en sede (152 docs)",
                "origen": "transparencia_sede",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)ordenanza", blob):
            tipo = "ordenanza"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm|bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|peri|planeam", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        rec = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "modelo licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Ordenanza o modelo de trámite; no concesión publicada",
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
        for doc in self._collect_ordenanzas_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "ordenanzas_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._collect_ordenanzas_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec:
                existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

        for doc in self._collect_ordenanzas_pdfs():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "ordenanzas_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
