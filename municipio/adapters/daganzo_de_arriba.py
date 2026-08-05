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

WEB_BASE = "https://www.ayto-daganzo.org"
SEDE_BASE = "https://daganzo.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
MUNICIPIO = "Daganzo de Arriba"
ID_PREFIX = "daganzo-de-arriba"
WFS_MUNICIPIO = "DAGANZO DE ARRIBA"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/avisos/normas-subsidiarias-de-planeamiento-1995",
    f"{WEB_BASE}/avisos/ordenanzas-municipales",
]

URBANISMO_TRAMITE_PAGES: list[str] = [
    f"{WEB_BASE}/sede-electronica/urbanismo",
    f"{WEB_BASE}/sede-electronica/urbanismo/licencia-para-la-ocupaci%C3%B3n-de-v%C3%ADa-p%C3%BAblica",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|actividad)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"ocupaci[oó]n de v[ií]a|ordenanza.*construc|licencia de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"urbanizaci[oó]n|expropiaci[oó]n|unidad de ejecuci[oó]n|\b(?:s|u)-\d+)",
)
RE_URBANISMO_PDF = re.compile(
    r"(?i)(urban|planeam|nnss|normas.?subsidiarias|bocm|construc|licen|obra|"
    r"plusvalia|dominio|anuncio|plano|clasificaci|ordenaci|gesti[oó]n|suelo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DATA_LABEL = re.compile(r'data-label="([^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://daganzo\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_MEDIA_LINK = re.compile(r'href="(/media/\d+/[^"]+\.pdf)"', re.I)
RE_LIST_GROUP = re.compile(
    r'class="list-group-item"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    m = re.search(r"BOCM[- ]?(\d{1,2})[- ](\d{1,2})[- ](\d{4})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "plano" in n:
        return "plano planeamiento"
    if "memoria" in n:
        return "memoria planeamiento"
    if "bocm" in n:
        return "publicación BOCM"
    if "ordenanza" in n:
        return "ordenanza municipal"
    if "licencia" in n:
        return "modelo licencia"
    return "documento urbanismo"


class DaganzoDeArribaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Fontventa (NNSS/ordenanzas) + tablón eHome espublico + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-daganzo-de-arriba/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href).replace("&amp;", "&"))

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_H1.search(html)
        if m:
            return _strip_html(m.group(1))[:500]
        m = re.search(r"<title>([^<]+)", html, re.I)
        if m:
            t = _strip_html(m.group(1))
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t:
                return t[:500]
        return fallback

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(WFS_MUNICIPIO, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": "https://idem.comunidad.madrid/geoserver3/ows",
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
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

    def _collect_planeamiento_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            section = self._page_title(html, page_url.rsplit("/", 1)[-1])

            for m in RE_LIST_GROUP.finditer(html):
                href, label_raw = m.group(1), m.group(2)
                label = _strip_html(label_raw)
                if not label or label.lower().startswith("ver documento"):
                    label = Path(unescape(href)).name.replace("-", " ")
                pdf_url = self._abs_web(href)
                if pdf_url in seen:
                    continue
                if not RE_URBANISMO_PDF.search(f"{label} {pdf_url}"):
                    continue
                seen.add(pdf_url)
                titulo = label if len(label) > 8 else f"{section}: {label}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{titulo} {pdf_url}"),
                        "tipo": _doc_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "planeamiento_web",
                        "section": section,
                    }
                )

            for m in RE_MEDIA_LINK.finditer(html):
                href = m.group(1)
                name = unescape(urllib.parse.unquote(Path(href).name))
                if not RE_URBANISMO_PDF.search(name):
                    continue
                pdf_url = self._abs_web(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                titulo = name if len(name) > 8 else f"{section}: {name}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{titulo} {pdf_url}"),
                        "tipo": _doc_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "planeamiento_web",
                        "section": section,
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = [
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
                "nota": "Documentación urbanismo en sede",
                "origen": "transparencia_sede",
            },
        ]
        for page_url in URBANISMO_TRAMITE_PAGES:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, "Trámite urbanismo")
            pages.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Información y requisitos del trámite",
                    "origen": "sede_tramites_web",
                }
            )
        return pages

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
        if row.get("categoria", "").lower() in {"urbanismo", "anuncios"} and RE_PROYECTO.search(blob):
            pass
        elif row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)ordenanza", blob):
            tipo = "ordenanza"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm|bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|peri|planeam|nnss", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)expropiaci", blob):
            tipo = "expropiación"
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

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
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

        for doc in self._collect_planeamiento_docs():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "planeamiento_web": sum(1 for r in rows if r.get("origen") == "planeamiento_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
