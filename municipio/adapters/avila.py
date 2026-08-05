from __future__ import annotations

import email.utils
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

WP_BASE = "https://www.avila.es"
SEDE_BASE = "https://sede.avila.es/GDCarpetaCiudadano"
MUNICIPIO = "Ávila"
ID_PREFIX = "avila"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
RSS_PLANEAMIENTO = (
    f"{WP_BASE}/areas-destacadas/urbanismo/planeamiento-urbanistico?format=feed&type=rss"
)
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "PLANEAM",
    "PGOU",
    "MODIFICACION",
    "INFORMACION PUBLICA",
    "EXPEDIENTE",
    "OBRA",
)

DEFAULT_LICENCIA_TRAMITE_URLS: list[str] = [
    f"{WP_BASE}/tramites/489-licencia-de-obra-menor",
    f"{WP_BASE}/tramites/490-licencia_de_obra_mayor",
    f"{WP_BASE}/tramites/491-licencia_ambiental",
    f"{WP_BASE}/tramites/495-comunicacin_ambiental",
    f"{WP_BASE}/tramites/710-instancia_cambio_de_titularidad",
    f"{WP_BASE}/tramites/712-comunicacin_inicio_de_actividad",
    f"{WP_BASE}/tramites/878-declaracin_responsable",
    f"{WP_BASE}/tramites/1151-inspeccion-tecnica-de-edificaciones-ite",
]

DEFAULT_URBANISMO_TRAMITE_URLS: list[str] = [
    f"{WP_BASE}/tramites/877-urbanismo",
    f"{WP_BASE}/tramites/1331-informe-de-adecuacion-de-vivienda-a-efectos-de-reagrupacion-familiar-o-renovacion-de-residencia",
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|ambiental|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"obra mayor|obra menor|primera ocupaci|ite\b|inspecci[oó]n t[eé]cnica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|"
    r"reparcel|estudio de detalle|sector|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"normalizaci[oó]n|exposici[oó]n p[uú]blica|actuaci[oó]n urban|aru\b)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|bolsa de empleo|agente de polic|t[eé]cnico de administraci[oó]n|"
    r"subvenci[oó]n deportiv|empadron|tribut|calendario fiscal|ordenanza fiscal)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TRAMITE_LINK = re.compile(r'href="(/tramites/\d+-[^"]+)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_rss_date(text: str) -> str | None:
    try:
        return email.utils.parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _proyecto_tipo(blob: str, default: str = "urbanismo") -> str:
    n = blob.lower()
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n:
        return "planeamiento"
    if "plan parcial" in n or "pp " in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "aprobaci" in n:
        return "aprobación"
    if "sector" in n:
        return "sector"
    return default


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


class AvilaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla K2 planeamiento + sede GDCarpetaCiudadano tablón + IDECyL WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.licencia_tramite_urls = [
            str(u) for u in (self.config.get("licencia_tramite_urls") or DEFAULT_LICENCIA_TRAMITE_URLS)
        ]
        self.urbanismo_tramite_urls = [
            str(u) for u in (self.config.get("urbanismo_tramite_urls") or DEFAULT_URBANISMO_TRAMITE_URLS)
        ]
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-avila/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset()
            if not charset:
                charset = "iso-8859-1" if "sede.avila.es" in url else "utf-8"
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        for layer, default_tipo in WFS_LAYERS:
            url = self._wfs_query_url(layer)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                titulo = _clean_title(str(props.get("n_titulo") or ""))
                if not titulo:
                    sector = str(props.get("n_sector") or "").strip()
                    num = str(props.get("n_num_sect") or "").strip()
                    titulo = f"{sector} ({num})" if sector else num
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("n_instrum") or props.get("c_instrum") or "")
                blob = f"{titulo} {instrum}"
                fecha = _parse_fecha_iso(str(props.get("f_bocyl") or "")) or _parse_fecha_iso(
                    str(props.get("f_aprob") or "")
                )
                doc_url = str(props.get("url_doc_info") or "").strip() or url
                key = str(props.get("c_id_sect") or props.get("c_plan") or props.get("fid") or titulo)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"wfs:{layer}:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob) if blob.strip() else default_tipo,
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "idecyl_wfs",
                    "wfs_layer": layer,
                    "sector_id": props.get("c_id_sect"),
                    "instrumento": instrum or None,
                }
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if titulo and len(titulo) > 8 and (titulo in wfs_title or wfs_title in titulo):
                for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
                return

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha": fecha_ini,
                "url": f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}",
                "expte": (m.group(1).strip() if (m := RE_EXPTE.search(title)) else None),
                "origen": "tablon",
            }
            if doc_m:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_m.group(1))
            by_id[ann_id] = rec
        return by_id

    def _parse_expte(text: str) -> str | None:
        m = RE_EXPTE.search(text or "")
        return m.group(1).strip() if m else None

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(TABLON_ALL, data=body)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            by_id.update(self._parse_tablon_html(self._fetch(TABLON_ALL)))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_rss_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml_text = self._fetch(RSS_PLANEAMIENTO)
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return rows
        for item in root.findall(".//item"):
            title = _clean_title(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            desc = item.findtext("description") or ""
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            pdfs = RE_PDF_HREF.findall(desc)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", link),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": fecha,
                "tipo": _proyecto_tipo(title),
                "url": link,
                "source": "ayuntamiento",
                "origen": "joomla_rss",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0] if pdfs[0].startswith("http") else f"{self.wp_base}{pdfs[0]}"
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _tramite_page_title(self, url: str) -> str | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        m = RE_H1.search(html)
        if m:
            return _clean_title(m.group(1))
        slug = url.rsplit("/", 1)[-1]
        return _clean_title(slug.split("-", 1)[-1].replace("-", " "))

    def _collect_tramite_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in self.licencia_tramite_urls:
            title = self._tramite_page_title(url)
            if not title:
                continue
            rec = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title,
                "url": url,
                "source": "ayuntamiento",
                "nota": "Trámite informativo del portal; no concesión publicada en tablón",
                "origen": "tramite_wp",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_tramite_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for base_url in self.urbanismo_tramite_urls:
            try:
                html = self._fetch(base_url)
            except urllib.error.URLError:
                continue
            for href in RE_TRAMITE_LINK.findall(html):
                url = href if href.startswith("http") else f"{self.wp_base}{href}"
                if "/tramites/877-" in url or url == base_url:
                    continue
                title = self._tramite_page_title(url)
                if not title or not RE_PROYECTO.search(title):
                    continue
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": None,
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_wp",
                }
                self._enrich_geometry(rec)
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia", blob):
            return None
        return {
            "id": _stable_id("lic", row.get("ann_id") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": row["expte"]} if row.get("expte") else {}),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        if RE_NOISE.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        key = row.get("pdf_url") or row.get("ann_id") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("expte"):
            rec["expte"] = row["expte"]
        self._enrich_geometry(rec)
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
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_tramite_licencias():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_wp"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for rec in self._collect_rss_proyectos():
            add(rec)
        for rec in self._collect_tramite_proyectos():
            add(rec)
        for rec in self._collect_tablon().values():
            add(self._row_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "rss": sum(1 for r in rows if r.get("origen") == "joomla_rss"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
