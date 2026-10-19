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

WEB_BASE = "https://www.gramenet.cat"
WFS_BASE = "https://www.gramenet.cat/geoserver/gramenetgis/wfs"
MUNICIPIO = "Santa Coloma de Gramenet"
ID_PREFIX = "santa-coloma-de-gramenet"

URBAN_BASE = (
    f"{WEB_BASE}/es/ayuntamiento/areas-municipales/"
    "planeamiento-urbanistico-informacion-urbanistica"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{URBAN_BASE}/",
    f"{URBAN_BASE}/expedientes-urbanisticos/",
    f"{URBAN_BASE}/expedientes-urbanisticos/planes-urbanisticos/planes-urbanisticos-derivados/",
    f"{URBAN_BASE}/expedientes-urbanisticos/estudios-de-detalle/",
    f"{URBAN_BASE}/expedientes-urbanisticos/convenios-urbanisticos/",
    f"{URBAN_BASE}/expedientes-urbanisticos/ordenaciones-volumetricas/",
    f"{URBAN_BASE}/expedientes-urbanisticos/otros-expedientes-urbanisticos/",
    f"{URBAN_BASE}/expedientes-en-tramite/",
    f"{URBAN_BASE}/gestion-urbanistica/",
    f"{WEB_BASE}/es/ayuntamiento/areas-municipales/licencias-y-disciplina-urbanistica/",
    f"{WEB_BASE}/seu-electronica/tramitacio/instancia-generica/",
    f"{WEB_BASE}/es/sede-electronica/cita-previa/",
]

WFS_POLYGON_LAYERS: list[tuple[str, str]] = [
    ("gramenetgis:eu_expurb_vigents_pu", "plan urbanístico"),
    ("gramenetgis:eu_expurb_vigents_ed", "estudio de detalle"),
    ("gramenetgis:eu_expurb_vigents_cu", "convenio urbanístico"),
    ("gramenetgis:eu_expurb_vigents_gu", "gestión urbanística"),
    ("gramenetgis:eu_expurb_vigents_ov", "ordenación volumétrica"),
    ("gramenetgis:gu_exp_gestio", "expediente gestión urbanística"),
    ("gramenetgis:eu_plansurb_tramit", "plan urbanístico en trámite"),
    ("gramenetgis:eu_estudidetall_tramit", "estudio de detalle en trámite"),
    ("gramenetgis:eu_conveniurb_tramit", "convenio urbanístico en trámite"),
    ("gramenetgis:eu_ordvolums_tramit", "ordenación volumétrica en trámite"),
    ("gramenetgis:gu_exp_gestio_tram", "gestión urbanística en trámite"),
    ("gramenetgis:eu_suspllic_tramit", "suspensión de licencias en trámite"),
]

RE_LINK = re.compile(
    r'href="((?:https://www\.gramenet\.cat)?/[^"#?]+\.(?:pdf|html)?[^"]*)"',
    re.I,
)
RE_GRAMENET_PATH = re.compile(
    r"(?i)/(?:es/ayuntamiento/areas-municipales/"
    r"planeamiento-urbanistico-informacion-urbanistica|"
    r"ajuntament/arees-municipals/planejament-urbanistic-informacio-urbanistica)"
    r"/[^\"#?]+",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|comunicaci[oó]n|declaraci[oó]n responsable|obra|activitat|actividad)",
)


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


def _proyecto_tipo(blob: str, default: str) -> str:
    n = (blob or "").lower()
    if "peri" in n or "reforma interior" in n:
        return "PERI"
    if "estudio" in n and "detall" in n:
        return "estudio de detalle"
    if "conveni" in n:
        return "convenio urbanístico"
    if "ordenaci" in n and "volum" in n:
        return "ordenación volumétrica"
    if "modificaci" in n and "pgm" in n:
        return "modificación PGM"
    if "plan parcial" in n or "pla parcial" in n:
        return "plan parcial"
    if "plan especial" in n or "pla especial" in n:
        return "plan especial"
    if "gesti" in n and "urban" in n:
        return "gestión urbanística"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "tramit" in n:
        return f"{default} en trámite"
    if "pla urban" in n or "plan urban" in n:
        return "plan urbanístico"
    return default or "planeamiento"


class SantaColomaDeGramenetAyuntamientoAdapter(AyuntamientoAdapter):
    """TYPO3 gramenet.cat + GeoServer WFS gramenetgis (geoportal Nexus)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": str(self.config.get("user_agent") or f"poc-bocm-{ID_PREFIX}/1.0"),
                "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urljoin(f"{self.web_base}/", unescape(href))

    def _wfs_page_url(self, layer: str, start_index: int) -> str:
        query: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": "500",
        }
        if start_index > 0:
            query["startIndex"] = str(start_index)
        params = urllib.parse.urlencode(query)
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for layer, default_tipo in WFS_POLYGON_LAYERS:
            start = 0
            while True:
                url = self._wfs_page_url(layer, start)
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                    break
                features = data.get("features") or []
                if not features:
                    break
                for feat in features:
                    if not isinstance(feat, dict):
                        continue
                    props = feat.get("properties") or {}
                    geom = feat.get("geometry")
                    cod = str(props.get("exp_cod_aj") or props.get("exp_cod_ge") or "").strip()
                    titulo = _strip_html(str(props.get("exp_nom") or cod or layer))
                    if not titulo:
                        continue
                    dedupe = cod or titulo.lower()
                    if dedupe in seen:
                        continue
                    seen.add(dedupe)
                    blob = f"{titulo} {props.get('exp_tipus') or ''} {props.get('exp_ambit') or ''}"
                    fecha = _parse_fecha_dmy(str(props.get("exp_daprov") or "")) or _parse_fecha_dmy(
                        str(props.get("exp_dpub") or "")
                    )
                    link = str(props.get("exp_link") or "").strip()
                    if link and not link.startswith("http"):
                        link = self._abs_url(link)
                    rec: dict[str, Any] = {
                        "id": _stable_id("proy", f"wfs:{layer}:{cod or titulo}"),
                        "municipio": MUNICIPIO,
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "tipo": _proyecto_tipo(blob, default_tipo),
                        "url": link or f"{WEB_BASE}/geoportal/",
                        "source": "ayuntamiento",
                        "origen": "geoserver_wfs",
                        "wfs_layer": layer,
                        "expediente_codigo": cod or None,
                        "expediente_tipo": props.get("exp_tipus"),
                        "expediente_ambito": props.get("exp_ambit"),
                    }
                    if isinstance(geom, dict) and geom.get("type"):
                        rec["geom_geojson"] = geom
                        rec["geometry_crs"] = "EPSG:4326"
                        rec["geometry_source"] = "portal_wfs_geoserver"
                        rec["geometry_source_url"] = url
                        rec["coord_source"] = "portal_geometry_centroid"
                        centroid = geometry_centroid(geom)
                        if centroid:
                            rec["lat"], rec["lon"] = centroid
                    rows.append(rec)
                matched = data.get("numberMatched") or data.get("totalFeatures")
                if isinstance(matched, int) and start + len(features) >= matched:
                    break
                if len(features) < 500:
                    break
                start += len(features)
        self._wfs_cache = rows
        return rows

    def _page_title(self, html: str, fallback: str) -> str:
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if not m:
            return fallback
        title = _strip_html(m.group(1))
        for sep in (":", "|"):
            if sep in title:
                title = title.split(sep, 1)[-1].strip()
        return title[:500] or fallback

    def _crawl_web_proyectos(self) -> list[dict[str, Any]]:
        urls: set[str] = set()
        for seed in self.seed_pages:
            if "licencias" in seed or "instancia-generica" in seed or "cita-previa" in seed:
                continue
            try:
                html = self._fetch(seed)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in RE_LINK.finditer(html):
                href = m.group(1)
                if not RE_GRAMENET_PATH.search(href):
                    continue
                abs_url = self._abs_url(href).rstrip("/")
                if abs_url.endswith(
                    (
                        "/planeamiento-urbanistico-informacion-urbanistica",
                        "/expedientes-urbanisticos",
                        "/expedientes-en-tramite",
                        "/gestion-urbanistica",
                    )
                ):
                    continue
                urls.add(abs_url)

        rows: list[dict[str, Any]] = []
        for url in sorted(urls):
            slug_part = url.rsplit("/", 1)[-1]
            if not slug_part or slug_part in ("es", "ayuntamiento"):
                continue
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                title = _strip_html(slug_part.replace("-", " "))
                html = ""
            else:
                title = self._page_title(html, _strip_html(slug_part.replace("-", " ")))
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"web:{url}"),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(title, "planeamiento"),
                "url": url,
                "source": "ayuntamiento",
                "origen": "web_typo3",
            }
            self._enrich_from_wfs(rec)
            rows.append(rec)
        return rows

    def _enrich_from_wfs(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        url = str(rec.get("url") or "")
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            wfs_url = str(wfs_rec.get("url") or "")
            if url and wfs_url and url.rstrip("/") == wfs_url.rstrip("/"):
                self._copy_geometry(rec, wfs_rec)
                return
            if titulo and wfs_title and (titulo in wfs_title or wfs_title in titulo):
                self._copy_geometry(rec, wfs_rec)
                return
            cod = str(wfs_rec.get("expediente_codigo") or "")
            if cod and cod.lower() in titulo:
                self._copy_geometry(rec, wfs_rec)
                return

    @staticmethod
    def _copy_geometry(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key in (
            "geom_geojson",
            "geometry_crs",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "expediente_codigo",
            "fecha",
        ):
            if source.get(key) is not None and target.get(key) is None:
                target[key] = source[key]

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        lic_urls = [
            f"{WEB_BASE}/es/ayuntamiento/areas-municipales/licencias-y-disciplina-urbanistica/",
            f"{WEB_BASE}/seu-electronica/tramitacio/instancia-generica/",
            f"{WEB_BASE}/es/sede-electronica/cita-previa/",
            f"{WEB_BASE}/fileadmin/Files/Ajuntament/cartes_serveis/25_cartes_catala_sense_any/13f_Carta_25_Disciplina.pdf",
        ]
        rows: list[dict[str, Any]] = []
        for url in lic_urls:
            try:
                html = self._fetch(url) if not url.endswith(".pdf") else ""
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            title = (
                self._page_title(html, "Licencias y disciplina urbanística")
                if html
                else "Carta de servicios — Disciplina urbanística y licencias"
            )
            if html and not RE_LICENCIA.search(title + " " + _strip_html(html)[:2000]):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sin tablón público de concesiones; páginas informativas OIAC / sede",
                }
            )
        return rows

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
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "licencias_info_pages"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for rec in self._crawl_web_proyectos():
            if rec["id"] in seen:
                continue
            dup = any(
                str(rec.get("url") or "").rstrip("/") == str(r.get("url") or "").rstrip("/")
                for r in rows
            )
            if not dup:
                add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "geoserver_wfs"),
            "web_typo3": sum(1 for r in rows if r.get("origen") == "web_typo3"),
            "with_geometry": with_geom,
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
        return {**result, "added": max(0, after - before)}
