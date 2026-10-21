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

SEDE_BASE = "https://sede.elejido.es/oficinavirtual"
TABLON_LIST = f"{SEDE_BASE}/tablonanuncios/listadoanuncios.php"
TABLON_INDEX = f"{SEDE_BASE}/tablonanuncios/index.php"
CATALOG_URL = f"{SEDE_BASE}/catalogopublico/index.php?op=ver_lista_por_area"
URBANISMO_WEB = "https://urbanismo.elejido.es"
SITUA_PGOU = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/"
    "planeamientoGeneralCompartir.jsf?municipiosSeleccionados=04051&codigosMunicipios=04051"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "El Ejido"
ID_PREFIX = "el-ejido"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal)?|"
    r"notificaci[oó]n.*licencia|comunicaci[oó]n previa de inicio de obra|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|replanteo)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|calificaci[oó]n ambiental|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|actuaci[oó]n urban|situa|vitua|edicto|licencia)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de (?:empleo|trabajo)|jurado sorteo|decreto luto|"
    r"resoluci[oó]n (?:definitiva|provisional) admitidos|bases para proveer)",
)
RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td>\s*<a href=\"([^\"]+detalleanuncio\.php\?id=(\d+))\">(.*?)</a>\s*</td>"
    r"\s*<td[^>]*>\s*(\d{2}/\d{2}/\d{4})\s*</td>"
    r".*?<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>\s*</tr>",
    re.I | re.S,
)
RE_MAX_PAGE = re.compile(r'data-page="(\d+)"[^>]*class="btn btn-arrow btn-arrow-allowed"[^>]*title="Última página"')
RE_MAX_PAGE_ALT = re.compile(r'title="Última página"[^>]*data-page="(\d+)"')
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

URBANISMO_AREAS = ("2", "16")  # Urbanismo, Desarrollo Urbanístico

PLANEAMIENTO_SEEDS: list[tuple[str, str]] = [
    (f"{URBANISMO_WEB}/planeamiento/", "Planeamiento urbanístico — portal Urbanismo"),
    (f"{URBANISMO_WEB}/modificaciones-de-planeamiento/", "Modificaciones de planeamiento"),
    (f"{URBANISMO_WEB}/instrumentos-de-planeamiento/", "Instrumentos de planeamiento"),
    (SITUA_PGOU, "PGOU / planeamiento general — SITUA (INE 04051)"),
    (SITUA_SEARCH, "Consulta planeamiento — SITUADIFusión Junta de Andalucía"),
]

LICENCIA_TRAMITES: list[tuple[str, str, str]] = [
    (
        f"{SEDE_BASE}/catalogopublico/index.php?area_id=4&op=buscar_por_area",
        "Catálogo — Actividades y licencias de Urbanismo",
        "catálogo urbanismo",
    ),
    (
        f"{SEDE_BASE}/catalogopublico/index.php?iframe=0&kiosko=0&op=ver_lista_por_area",
        "Catálogo público de procedimientos",
        "catálogo trámites",
    ),
    (TABLON_INDEX, "Tablón de anuncios y edictos — sede electrónica", "tablón de anuncios"),
    (
        "https://elejido.es/callejero/",
        "Callejero municipal (Leaflet + GeoJSON calles/números)",
        "callejero",
    ),
]


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str) -> str:
    blob = title.lower()
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "calificaci" in blob and "ambiental" in blob:
        return "calificación ambiental"
    if "licencia" in blob:
        return "licencia publicada"
    if "modificaci" in blob and "planeamiento" in blob:
        return "modificación planeamiento"
    if "pgou" in blob or "planeamiento general" in blob:
        return "PGOU"
    if "planeamiento" in blob or "urban" in blob:
        return "planeamiento"
    return "urbanismo"


class ElEjidoAyuntamientoAdapter(AyuntamientoAdapter):
    """Oficina Virtual propia (PHP): tablón AJAX + catálogo; web WP urbanismo.elejido.es."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_list = str(self.config.get("tablon_list_url") or TABLON_LIST)
        self.urbanismo_areas = tuple(
            str(a) for a in (self.config.get("tablon_areas") or URBANISMO_AREAS)
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-ejido/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _tablon_page_url(self, pagina: int, numero_filas: int, area: str | None) -> str:
        params: dict[str, str | int] = {"pagina": pagina, "numero_filas": numero_filas}
        if area:
            params["area"] = area
        return f"{self.tablon_list}?{urllib.parse.urlencode(params)}"

    def _max_page(self, html: str) -> int:
        m = RE_MAX_PAGE.search(html) or RE_MAX_PAGE_ALT.search(html)
        if m:
            return max(1, int(m.group(1)))
        pages = [int(x) for x in re.findall(r'data-page="(\d+)"', html)]
        return max(pages) if pages else 1

    def _parse_tablon_page(self, html: str, area_label: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            url, ann_id, title_html, fecha_raw, origen, tipo_anuncio = m.groups()
            titulo = _strip_html(title_html)
            if not titulo:
                continue
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            fecha = _parse_fecha_dmy(fecha_raw)
            blob = f"{titulo} {origen} {tipo_anuncio}"
            rows.append(
                {
                    "anuncio_id": ann_id,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "origen_area": origen.strip(),
                    "tipo_anuncio": tipo_anuncio.strip(),
                    "area_filter": area_label,
                    "blob": blob,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        per_page = int(self.config.get("tablon_page_size", 50))

        for area in self.urbanismo_areas:
            try:
                first = self._fetch(self._tablon_page_url(1, per_page, area))
            except urllib.error.URLError:
                continue
            max_p = self._max_page(first)
            max_pages_cap = int(self.config.get("tablon_max_pages", max_p))
            last_page = min(max_p, max_pages_cap)

            for page in range(1, last_page + 1):
                try:
                    html = first if page == 1 else self._fetch(
                        self._tablon_page_url(page, per_page, area)
                    )
                except urllib.error.URLError:
                    break
                for row in self._parse_tablon_page(html, area):
                    key = row["anuncio_id"]
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(row)
        return out

    def _collect_planeamiento_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in PLANEAMIENTO_SEEDS:
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": None,
                    "url": url,
                    "blob": f"{titulo} planeamiento urbanismo El Ejido",
                    "origen": "urbanismo_web",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        for url, titulo, tipo in LICENCIA_TRAMITES:
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
                    "nota": "Trámite informativo; concesiones publicadas en tablón de anuncios",
                    "origen": "sede_tramite",
                }
            )
        return pages

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_TABLON_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("anuncio_id") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
            "area": row.get("origen_area"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_TABLON_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("anuncio_id") or row["url"]
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

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "urbanismo_web"),
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

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_planeamiento_seeds():
            add(self._seed_to_proyecto(item))
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
            "info": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
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
            "seeds": sum(1 for r in rows if r.get("origen") != "tablon"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_proyectos():
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
