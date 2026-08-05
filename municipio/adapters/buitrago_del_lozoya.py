from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

SITE_BASE = "https://www.buitrago.org"
SEDE_BASE = "https://buitragodellozoya.sedelectronica.es"
MUNICIPIO = "Buitrago del Lozoya"
ID_PREFIX = "buitrago-del-lozoya"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "BUITRAGO DEL LOZOYA"

DEFAULT_SEED_PAGES: list[str] = [
    f"{SITE_BASE}/normativa/urbanismo",
    f"{SITE_BASE}/tramites/de-urbanismo",
    f"{SITE_BASE}/inicio/tablon-municipal",
]

RSS_FEEDS: list[str] = [
    f"{SITE_BASE}/normativa/urbanismo?format=feed&type=rss",
    f"{SITE_BASE}/inicio/tablon-municipal?format=feed&type=rss",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|acto menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|urbanizaci[oó]n|estudio de detalle|bocm|edicto|bando.*(?:obra|calle)|"
    r"exposici[oó]n p[uú]blica|las roturas|matadero|sau[\-\s]?\d|ug[\-\s]?\d|"
    r"\b(?:SAU|UG|UE|AD|AN|AI|PAU|S)-[\w\d-]+\b|plantas solares|infraestructuras)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|igualdad|incendio|emergencias|"
    r"calendario laboral|censo electoral|residencia.*mayores|reglamento.*residencia|"
    r"ciberseguridad|medicamentos|aemps|fiestas|cursos de formaci[oó]n|"
    r"convenio.*festival|convenio.*regata|eclipse)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?buitrago\.org)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_BOARD_PREVIEW = re.compile(
    r'href="(https://buitragodellozoya\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:images/stories|uploads)/(?:[^/]+/)*(\d{4})/(\d{2})/")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})")
RE_ARTICLE_LINK = re.compile(
    r'href="((?:https://www\.buitrago\.org)?/(?:normativa/urbanismo|inicio/tablon-municipal)/\d+-[^"]+)"',
    re.I,
)


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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_BOCM_DATE.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _fecha_from_url(text)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bsau[\-\s]?\d", n) or "plan parcial" in n:
        return "plan parcial"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan especial" in n or "infraestructuras" in n or "solar" in n:
        return "plan especial"
    if "urbanizaci" in n or "las roturas" in n:
        return "urbanización"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación puntual"
    if "aprobaci" in n:
        return "aprobación"
    if "bando" in n:
        return "bando municipal"
    return "urbanismo"


class BuitragoDelLozoyaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla (normativa urbanismo, tablón) + sede espublico + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SITE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.site_base = str(self.config.get("site_base") or SITE_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.rss_feeds = [str(u) for u in (self.config.get("rss_feeds") or RSS_FEEDS)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-buitrago-del-lozoya/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_site(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.site_base}/", href)

    def _parse_joomla_rss(self, url: str) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(url)
            root = ElementTree.fromstring(xml_text)
        except (urllib.error.URLError, ElementTree.ParseError):
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        rows: list[dict[str, Any]] = []
        channel = root.find("channel")
        if channel is None:
            return rows

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = _parse_rss_date(item.findtext("pubDate") or "")
            desc = item.findtext("description") or ""
            pdfs: list[tuple[str, str]] = []
            for m in RE_PDF_HREF.finditer(desc):
                pdf_url = self._abs_site(m.group(1))
                label = _strip_html(m.group(0)) or Path(urllib.parse.urlparse(pdf_url).path).name
                pdfs.append((pdf_url, label))
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": pub,
                    "url": link,
                    "pdf_url": pdfs[0][0] if pdfs else None,
                    "pdfs": pdfs,
                    "origen": "joomla_rss",
                    "feed": url,
                }
            )
        return rows

    def _parse_page_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        page_title_m = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
        page_title = _strip_html(page_title_m.group(1)) if page_title_m else page_url

        for m in RE_PDF_HREF.finditer(html):
            pdf_url = self._abs_site(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            anchor_m = re.search(
                rf'href=["\']{re.escape(m.group(1))}["\'][^>]*>(.*?)</a>',
                html[m.start() : m.end() + 300],
                re.I | re.S,
            )
            label = _strip_html(anchor_m.group(1)) if anchor_m else Path(urllib.parse.urlparse(pdf_url).path).name
            titulo = label if len(label) > 8 else f"{page_title} — {label}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "joomla_pdf",
                }
            )
        return rows

    def _collect_category_pages(self, base_path: str, max_pages: int = 8) -> list[str]:
        urls: list[str] = []
        for start in range(0, max_pages * 20, 20):
            page_url = f"{self.site_base}{base_path}" + (f"?start={start}" if start else "")
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                break
            found = RE_ARTICLE_LINK.findall(html)
            if not found:
                break
            for href in found:
                full = self._abs_site(href)
                if full not in urls:
                    urls.append(full)
            if 'aria-label="Ir a la página siguiente"' not in html and start > 0:
                break
        return urls

    def _collect_joomla(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}

        for feed_url in self.rss_feeds:
            for rec in self._parse_joomla_rss(feed_url):
                key = rec.get("pdf_url") or rec["url"]
                by_key[key] = rec

        for base_path in ("/normativa/urbanismo", "/inicio/tablon-municipal"):
            for article_url in self._collect_category_pages(base_path):
                try:
                    html = self._fetch(article_url)
                except urllib.error.URLError:
                    continue
                title_m = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
                title = _strip_html(title_m.group(1)) if title_m else article_url
                date_m = re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)
                fecha = date_m.group(1)[:10] if date_m else None
                pdfs = self._parse_page_pdfs(html, article_url)
                if pdfs:
                    for pdf_rec in pdfs:
                        key = pdf_rec["pdf_url"]
                        by_key[key] = pdf_rec
                else:
                    key = article_url
                    by_key[key] = {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": article_url,
                        "origen": "joomla_article",
                    }

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_page_pdfs(html, page_url):
                key = rec["pdf_url"]
                by_key[key] = rec

        return list(by_key.values())

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if tbody_m:
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
        if not rows:
            for m in RE_BOARD_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 400) : m.end() + 200]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1).strip()) if title_m else url
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "pdf_url": url,
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
        tramites_url = f"{self.site_base}/tramites/de-urbanismo"
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites de urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — formularios PDF",
                "url": tramites_url,
                "source": "ayuntamiento",
                "nota": "Formularios licencia obra, parcelación, actos menores (Joomla)",
                "origen": "joomla_tramite",
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
                "nota": "Anuncios y exposiciones públicas (espublico gestiona)",
                "origen": "sede_tablon",
            },
        ]
        try:
            html = self._fetch(tramites_url)
        except urllib.error.URLError:
            return rows
        for m in re.finditer(
            r'<a[^>]+href="([^"]+\.pdf)"[^>]*>([^<]+)</a>',
            html,
            re.I,
        ):
            pdf_url = self._abs_site(m.group(1))
            label = _strip_html(m.group(2))
            if not RE_LICENCIA.search(label):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": None,
                    "tipo": "formulario licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": label[:500],
                    "url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "joomla_form",
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

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(titulo):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
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
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": f"{self.site_base}/normativa/urbanismo",
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

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"] + "|" + row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria")
        )
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
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
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
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("joomla", "sede_tablon"))),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
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

        for item in self._collect_joomla():
            add(self._to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "joomla": sum(1 for r in rows if str(r.get("origen", "")).startswith("joomla")),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
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
