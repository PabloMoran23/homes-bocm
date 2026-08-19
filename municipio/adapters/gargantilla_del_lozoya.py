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
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://gargantillaypinilla.madrid"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
LIFERAY_BASE = "https://www.gargantilla.es"
SEDE_BASE = "https://gargantillaypinilla.sedelectronica.es"
MUNICIPIO = "Gargantilla del Lozoya"
ID_PREFIX = "gargantilla-del-lozoya"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "GARGANTILLA DEL LOZOYA Y PINILLA DE BUITRAGO"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/plan-general-de-ordenacion-urbana/",
    f"{WP_BASE}/ordenanzas/",
    f"{WP_BASE}/documentos-municipales/",
    f"{LIFERAY_BASE}/urbanismo",
]

WP_SEARCH_TERMS: list[str] = [
    "pgou",
    "urbanismo",
    "ordenanza urban",
    "licencia obra",
    "planeamiento",
    "informacion publica",
    "construccion",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|urbanizaci[oó]n|bocm|edicto|ordenanza.*urban|pol[ií]gono|"
    r"plusval[ií]a|ocupaci[oó]n.*suelo|tasa.*licencia|construcci[oó]n.*recinto|"
    r"\b(?:UE|AD|AN|AI|PAU|S)-[\w\d-]+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|igualdad|piscina|campamento|"
    r"calendario fiscal|ibi\b|plusvalia municipal|sepultura|cementerio|fisioterapia|"
    r"campamentos infantiles|domiciliaci[oó]n|certificado.*nacimiento|defunci[oó]n|"
    r"matrimonio|fiestas patronales|prevenci[oó]n.*incendio|antifraude|rabia)",
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_LINK_LABEL = re.compile(
    r'href=["\']([^"\']+)["\'][^>]*>([^<]{3,})</a>',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})")
RE_POLIGONO = re.compile(r"(?i)pol[ií]gono\s*(\d+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_BOCM_DATE.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _fecha_from_url(text)


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "polígono" in n or "poligono" in n:
        return "polígono PGOU"
    if "ordenanza" in n and "urban" in n:
        return "ordenanza urbanística"
    if "plusval" in n:
        return "ordenanza fiscal"
    if "ocupaci" in n and "suelo" in n:
        return "ordenanza fiscal urbanística"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "construcci" in n and "recinto" in n:
        return "obra pública"
    if "modificaci" in n:
        return "modificación ordenanza"
    if "aprobaci" in n:
        return "aprobación"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "declaraci" in n and "responsable" in n:
        return "declaración responsable"
    if "licencia" in n and "obra" in n:
        return "licencia de obra"
    if "tasa" in n and "licencia" in n:
        return "tasa licencias urbanísticas"
    return "trámite licencia urbanística"


class GargantillaDelLozoyaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + Liferay legacy + sede espublico + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = f"{self.wp_base}/wp-json/wp/v2"
        self.liferay_base = str(self.config.get("liferay_base") or LIFERAY_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_search_terms = [
            str(t) for t in (self.config.get("wp_search_terms") or WP_SEARCH_TERMS)
        ]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _parse_page_links(self, html: str, page_url: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LINK_LABEL.finditer(html):
            href = m.group(1)
            if href.startswith("#"):
                continue
            label = _strip_html(m.group(2))
            if not label:
                continue
            abs_url = self._abs_wp(href) if "gargantilla" in href or href.startswith("/") else href
            if abs_url in seen:
                continue
            seen.add(abs_url)
            rec: dict[str, Any] = {
                "titulo": label[:500],
                "fecha": _fecha_from_url(abs_url) or _fecha_from_blob(label),
                "url": page_url,
                "origen": origen,
            }
            if abs_url.lower().endswith(".pdf"):
                rec["pdf_url"] = abs_url
            rows.append(rec)
        return rows

    def _collect_wp_pages(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for page_url in self.seed_pages:
            if not page_url.startswith(self.wp_base):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_page_links(html, page_url, "wp_page"):
                key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
                by_key[key] = rec
        return list(by_key.values())

    def _collect_wp_api_pages(self) -> list[dict[str, Any]]:
        slugs = ("plan-general-de-ordenacion-urbana", "ordenanzas", "documentos-municipales")
        rows: list[dict[str, Any]] = []
        for slug in slugs:
            try:
                data = self._fetch_json(f"{self.wp_api}/pages?slug={slug}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list) or not data:
                continue
            page = data[0]
            page_url = str(page.get("link") or f"{self.wp_base}/{slug}/")
            content = (page.get("content") or {}).get("rendered", "")
            fecha = _iso_date_wp(str(page.get("modified") or page.get("date") or ""))
            for m in RE_LINK_LABEL.finditer(content):
                href = m.group(1)
                if href.startswith("#"):
                    continue
                label = _strip_html(m.group(2))
                if not label:
                    continue
                abs_url = self._abs_wp(href)
                rec: dict[str, Any] = {
                    "titulo": label[:500],
                    "fecha": _fecha_from_url(abs_url) or fecha,
                    "url": page_url,
                    "origen": "wp_api_page",
                }
                if abs_url.lower().endswith(".pdf"):
                    rec["pdf_url"] = abs_url
                rows.append(rec)
            if slug == "plan-general-de-ordenacion-urbana":
                rows.append(
                    {
                        "titulo": "PGOU — Documento de Aprobación Provisional (TransferNow)",
                        "fecha": fecha,
                        "url": page_url,
                        "origen": "wp_pgou",
                    }
                )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for term in self.wp_search_terms:
            page = 1
            while page <= 3:
                params = urllib.parse.urlencode(
                    {
                        "search": term,
                        "per_page": "100",
                        "page": str(page),
                        "_fields": "id,link,title,date,content",
                    }
                )
                try:
                    posts = self._fetch_json(f"{self.wp_api}/posts?{params}")
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    if not isinstance(post, dict):
                        continue
                    link = str(post.get("link") or "")
                    title = _strip_html((post.get("title") or {}).get("rendered", ""))
                    if not link or not title:
                        continue
                    content = (post.get("content") or {}).get("rendered", "")
                    rec: dict[str, Any] = {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": link,
                        "origen": "wp_post",
                    }
                    for pm in RE_PDF_HREF.finditer(content):
                        pdf_url = self._abs_wp(pm.group(1))
                        pdf_rec = {
                            **rec,
                            "pdf_url": pdf_url,
                            "fecha": _fecha_from_url(pdf_url) or rec["fecha"],
                        }
                        by_key[pdf_url] = pdf_rec
                    by_key.setdefault(link, rec)
                if len(posts) < 100:
                    break
                page += 1
        return list(by_key.values())

    def _collect_liferay(self) -> list[dict[str, Any]]:
        url = f"{self.liferay_base}/urbanismo"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        return self._parse_page_links(html, url, "liferay_urbanismo")

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return rows
        for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
            row_html = row_m.group(1)
            if "emptyRow" in row_html:
                continue
            cells: dict[str, str] = {}
            doc_url = self.board_url
            for cm in RE_BOARD_CELL.finditer(row_html):
                label, val = cm.group(1), cm.group(2)
                link_m = re.search(r'href="([^"]+)"', val, re.I)
                if link_m:
                    doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                cells[label] = _strip_html(val)
            titulo = cells.get("Descripción") or cells.get("Documento") or ""
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells.get("Expediente", ""),
                    "procedimiento": cells.get("Procedimiento", ""),
                    "categoria": cells.get("Categoría", ""),
                    "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                    "url": doc_url,
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        docs_url = f"{self.wp_base}/documentos-municipales/"
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", docs_url),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Documentos municipales — licencias y declaraciones",
                "url": docs_url,
                "source": "ayuntamiento",
                "origen": "wp_tramite",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "espublico gestiona (vacío al scrapear)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
        ]
        for item in self._collect_wp_api_pages():
            blob = f"{item.get('titulo', '')} {item.get('pdf_url', '')}"
            if not RE_LICENCIA.search(blob):
                continue
            key = item.get("pdf_url") or item["url"]
            rows.append(
                {
                    "id": _stable_id("lic", key),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": _licencia_tipo(item.get("titulo") or ""),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item.get("pdf_url") or item["url"],
                    "source": "ayuntamiento",
                    "origen": item.get("origen"),
                    **({"pdf_url": item["pdf_url"]} if item.get("pdf_url") else {}),
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            pm = RE_POLIGONO.search(name)
            if pm:
                cache.setdefault(f"POLIGONO {pm.group(1)}", f)
                cache.setdefault(f"POLÍGONO {pm.group(1)}", f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(titulo):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            cache = self._load_wfs_ambitos()
            pm = RE_POLIGONO.search(titulo or "")
            if pm:
                feat = cache.get(f"POLÍGONO {pm.group(1)}") or cache.get(f"POLIGONO {pm.group(1)}")
                if feat:
                    geom = _merge_geometries([feat])
                    meta = {"ambito_name": str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "")}
        if not geom:
            return None
        name = str(meta.get("ambito_name") or "")
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
        ) if name else ""
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                if cql
                else self.wfs_url
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": name or None,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        by_name: dict[str, list[dict[str, Any]]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if name:
                by_name.setdefault(name, []).append(f)
        rows: list[dict[str, Any]] = []
        for name, group in by_name.items():
            merged = _merge_geometries(group)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": name[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": f"{self.wp_base}/plan-general-de-ordenacion-urbana/",
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("expediente") or row["url"] + "|" + row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("titulo") or ""),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria"))
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

    def _collect_source_rows(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wp_pages():
            key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
            by_key[key] = rec
        for rec in self._collect_wp_api_pages():
            key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
            by_key.setdefault(key, rec)
        for rec in self._collect_wp_posts():
            key = rec.get("pdf_url") or rec["url"]
            by_key.setdefault(key, rec)
        for rec in self._collect_liferay():
            key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
            by_key.setdefault(key, rec)
        for rec in self._collect_board():
            key = rec.get("expediente") or rec["url"]
            by_key.setdefault(key, rec)
        return list(by_key.values())

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
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("wp_", "sede_"))),
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

        for item in self._collect_source_rows():
            add(self._row_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
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
