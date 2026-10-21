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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.santander.es"
SEDE_BASE = "https://sede.santander.es"
MUNICIPIO = "Santander"
ID_PREFIX = "santander"

SIUCAN_MS = "https://geoservicios.cantabria.es/inspire/rest/services/Urbanismo/MapServer"
SIUCAN_SECTORES_LAYER = 1

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ciudad/pgs/informacion-publica",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/estudios-detalle",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/unidades-actuacion",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/sectores",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/modificaciones-pgs",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/plan-especfico-parciales",
    f"{WEB_BASE}/ciudad/pgs/en-vigor/concrecion-equipamiento",
    f"{WEB_BASE}/ciudad/pgs/pgs-redaccion",
    f"{SEDE_BASE}/tablon-de-edictos/otros-anuncios",
]

DEFAULT_TRAMITE_SLUGS: tuple[str, ...] = (
    "solicitud-licencia-obra-menor",
    "solicitud-licencia-obra-mayor-nueva-planta",
    "solicitud-licencia-obra-mayor-reformas-ampliaciones-edificiosinstalaciones-comerciales",
    "solicitud-licencia-obra-mayor-derribo",
    "declaracion-responsable-obra-menor-ocupacion-publica",
    "declaracion-responsable-obra-menor-sin-ocupacion-publica",
    "licencia-colocacion-medio-auxiliar",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|obra (?:mayor|menor)|declaraci[oó]n responsable|"
    r"derribo|colocaci[oó]n|autorizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|pgou|pgs|informaci[oó]n p[uú]blica|expediente|"
    r"estudio de detalle|modificaci[oó]n|sector|unidad de actuaci|"
    r"reparto|concreci[oó]n|equipamiento|expropi|reversi[oó]n|plan (?:parcial|especial))",
)
RE_NOISE = re.compile(
    r"(?i)(jurado|candidatos|notificaciones pendientes|citaci[oó]n a interesados)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
RE_FECHA_BOC = re.compile(r"BOC\s+(\d{1,2})-(\d{1,2})-(\d{4})", re.I)
RE_PDF_HREF = re.compile(
    r'href="((?:https?:)?//www\.santander\.es/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_STRONG_LI = re.compile(r"<li>\s*<strong>(.*?)</strong>", re.S | re.I)
RE_TABLON_TR = re.compile(
    r'<tr class="[^"]*views-row[^"]*">(.*?)</tr>',
    re.S | re.I,
)
RE_TABLON_LINK = re.compile(r'href="(/publicaciones/tablon-anuncios/[^"]+)"', re.I)
RE_TABLON_FECHA = re.compile(
    r'views-field-field-fecha-exposicion-edictos[^>]*>\s*([^<]+)\s*<',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_BOC, RE_FECHA_DMY):
        m = pat.search(text or "")
        if not m:
            continue
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            continue
    years = [
        int(y.group(1))
        for y in re.finditer(r"\b((?:19|20)\d{2})\b", text or "")
        if 1990 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "concreci" in n and "equipamiento" in n:
        return "concreción equipamiento"
    if "expropi" in n or "reversi" in n:
        return "expropiación / reversión"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "plan parcial" in n or "plan espec" in n:
        return "plan parcial"
    if "unidad de actuaci" in n:
        return "unidad de actuación"
    if "sector" in n:
        return "sector urbanístico"
    return "planeamiento"


class SantanderAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 (PGS) + sede tablón edictos + SIUCAN ArcGIS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tramite_slugs = tuple(self.config.get("tramite_slugs") or DEFAULT_TRAMITE_SLUGS)
        self.siucan_ms = str(self.config.get("siucan_mapserver") or SIUCAN_MS).rstrip("/")
        self._sector_index: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santander/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santander/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_web(self, href: str, page_url: str) -> str:
        if href.startswith("//"):
            return "https:" + href
        return urljoin(page_url, href)

    def _field_contenido(self, html: str) -> str:
        m = re.search(
            r'field-name-field-contenido[^>]*>.*?<div class="field-items">(.*?)</div>\s*</div>\s*</div>',
            html,
            re.S | re.I,
        )
        return m.group(1) if m else html

    def _parse_strong_sections(self, html: str, page_url: str, origen: str) -> list[dict[str, Any]]:
        body = self._field_contenido(html)
        rows: list[dict[str, Any]] = []
        parts = re.split(r"(?=<li>\s*<strong>)", body, flags=re.I)
        for chunk in parts:
            m = RE_STRONG_LI.search(chunk)
            if not m:
                continue
            titulo = _strip_html(m.group(1))
            if len(titulo) < 8:
                continue
            if RE_NOISE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            pdfs = [self._abs_web(h, self.web_base) for h in RE_PDF_HREF.findall(chunk)]
            boc_m = re.search(
                r'href="(https://boc\.cantabria\.es/[^"]+)"',
                chunk,
                re.I,
            )
            url = boc_m.group(1) if boc_m else (pdfs[0] if pdfs else page_url)
            fecha = _parse_fecha_dmy(chunk) or _parse_fecha_dmy(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "pdf_urls": pdfs[:12],
                    "origen": origen,
                }
            )
        return rows

    def _parse_informacion_publica(self, html: str, page_url: str) -> list[dict[str, Any]]:
        body = self._field_contenido(html)
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r"<ul>\s*<li>(.*?)</li>\s*</ul>\s*<ol[^>]*>(.*?)</ol>",
            body,
            re.S | re.I,
        ):
            titulo = _strip_html(m.group(1))
            if not titulo or not RE_PROYECTO.search(titulo):
                continue
            chunk = m.group(2)
            pdfs = [self._abs_web(h, self.web_base) for h in RE_PDF_HREF.findall(chunk)]
            fecha = _parse_fecha_dmy(chunk) or _parse_fecha_dmy(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": pdfs[0] if pdfs else page_url,
                    "pdf_urls": pdfs[:12],
                    "origen": "informacion_publica",
                }
            )
        rows.extend(self._parse_strong_sections(html, page_url, "pgs_drupal"))
        return rows

    def _parse_tablon(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in RE_TABLON_TR.findall(html):
            if "views-field-title" not in tr:
                continue
            link_m = RE_TABLON_LINK.search(tr)
            if not link_m:
                continue
            title_m = re.search(r"views-field-title[^>]*>\s*<a[^>]*>([^<]+)</a>", tr, re.I)
            if not title_m:
                continue
            titulo = _strip_html(title_m.group(1))
            if RE_NOISE.search(titulo):
                continue
            unidad_m = re.search(r"views-field-title[^>]*>.*?</td>\s*<td[^>]*>\s*([^<]+)", tr, re.S | re.I)
            unidad = _strip_html(unidad_m.group(1)) if unidad_m else ""
            fecha_m = RE_TABLON_FECHA.search(tr)
            fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else None
            url = urljoin(f"{self.sede_base}/", link_m.group(1))
            blob = f"{titulo} {unidad}"
            if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "unidad": unidad,
                    "origen": "tablon_edictos",
                    "is_licencia": bool(RE_LICENCIA.search(blob)),
                }
            )
        return rows

    def _collect_tramites_licencia(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug in self.tramite_slugs:
            url = f"{self.sede_base}/tramites/{slug}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r"<h2[^>]*class=\"titulo\"[^>]*>.*?</h2>\s*<h2[^>]*>([^<]+)", html, re.S | re.I)
            title_m = re.search(r"<title>([^<|]+)", html, re.I)
            titulo = _strip_html(h1_m.group(1) if h1_m else title_m.group(1) if title_m else slug)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia de obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:300],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _load_sector_index(self) -> list[dict[str, Any]]:
        if self._sector_index is not None:
            return self._sector_index
        params = urllib.parse.urlencode(
            {
                "where": "NomMuni='Santander'",
                "outFields": "CodSect,DenSect",
                "returnGeometry": "false",
                "f": "json",
                "resultRecordCount": "200",
            }
        )
        url = f"{self.siucan_ms}/{SIUCAN_SECTORES_LAYER}/query?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._sector_index = []
            return self._sector_index
        feats = data.get("features") or []
        self._sector_index = [
            {
                "cod": str((f.get("attributes") or {}).get("CodSect") or ""),
                "den": str((f.get("attributes") or {}).get("DenSect") or ""),
            }
            for f in feats
            if (f.get("attributes") or {}).get("CodSect")
        ]
        return self._sector_index

    def _sector_where_clause(self, titulo: str) -> str | None:
        t = titulo.upper()
        cod_m = re.search(r"\bS-(\d+)\b", t)
        if cod_m:
            return f"NomMuni='Santander' AND CodSect='S-{cod_m.group(1)}'"
        sec_m = re.search(r"SECTOR\s+(\d+)", t)
        if sec_m:
            return f"NomMuni='Santander' AND CodSect='S-{sec_m.group(1)}'"
        quoted = re.findall(r'"([^"]{4,40})"', titulo)
        for q in quoted:
            qlow = q.lower()
            hits = [row for row in self._load_sector_index() if qlow in row["den"].lower()]
            if len(hits) == 1:
                esc = hits[0]["cod"].replace("'", "''")
                return f"NomMuni='Santander' AND CodSect='{esc}'"
        # Denominación explícita entre comillas en títulos tipo UA-R11.19 … "LOS ALEBRIJES"
        m = re.search(r'AR\s*\d+[^"]*"([^"]{5,60})"', titulo, re.I)
        if m:
            needle = m.group(1).lower()
            hits = [row for row in self._load_sector_index() if needle in row["den"].lower()]
            if len(hits) == 1:
                esc = hits[0]["cod"].replace("'", "''")
                return f"NomMuni='Santander' AND CodSect='{esc}'"
        return None

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        where = self._sector_where_clause(titulo)
        if not where:
            return None
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "CodSect,DenSect",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            }
        )
        url = f"{self.siucan_ms}/{SIUCAN_SECTORES_LAYER}/query?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None
        feats = data.get("features") or []
        if not feats:
            return None
        geom = feats[0].get("geometry")
        if not isinstance(geom, dict) or not geom.get("type"):
            return None
        return {
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        pack = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not pack:
            return
        rec.update(pack)
        centroid = geometry_centroid(pack["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _proyecto_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        titulo = raw["titulo"]
        key = f"{titulo}|{raw.get('url')}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": raw.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": raw.get("url"),
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        if raw.get("pdf_urls"):
            rec["pdf_urls"] = raw["pdf_urls"]
        if raw.get("unidad"):
            rec["unidad_tramitadora"] = raw["unidad"]
        self._enrich_geometry(rec)
        return rec

    def _collect_proyectos_raw(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            if "informacion-publica" in page_url:
                parsed = self._parse_informacion_publica(html, page_url)
            elif "tablon-de-edictos" in page_url:
                parsed = [r for r in self._parse_tablon(html) if not r.get("is_licencia")]
            else:
                parsed = self._parse_strong_sections(html, page_url, "pgs_drupal")
            for raw in parsed:
                key = f"{raw['titulo']}|{raw.get('url')}"
                by_key[key] = raw
        return list(by_key.values())

    def _collect_licencias_raw(self) -> list[dict[str, Any]]:
        rows = self._collect_tramites_licencia()
        try:
            html = self._fetch(f"{self.sede_base}/tablon-de-edictos/otros-anuncios")
        except urllib.error.URLError:
            return rows
        for raw in self._parse_tablon(html):
            if not raw.get("is_licencia"):
                continue
            titulo = raw["titulo"]
            rows.append(
                {
                    "id": _stable_id("lic", f"{titulo}|{raw['url']}"),
                    "fecha_concesion": raw.get("fecha"),
                    "tipo": "licencia / edicto urbanístico",
                    "distrito": raw.get("unidad"),
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": raw["url"],
                    "source": "ayuntamiento",
                    "origen": "tablon_edictos",
                }
            )
        return rows

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
        rows = self._collect_licencias_raw()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_raw():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = [self._proyecto_row(r) for r in self._collect_proyectos_raw()]
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
