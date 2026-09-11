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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.cardenosa.es"
RSS_URL = f"{WEB_BASE}/rss.xml"
SEDE_BASE = "https://cardenosa.sedelectronica.es"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
MUNICIPIO = "Cardeñosa"
ID_PREFIX = "cardenosa"

WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
WFS_MUNICIPIO = "Cardeñosa"
WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ayuntamiento/normas-urbanisticas/",
    f"{WEB_BASE}/ayuntamiento/tablon-de-anuncios/",
    f"{WEB_BASE}/ayuntamiento/anuncios-boletines/",
    f"{WEB_BASE}/ayuntamiento/bandos/",
    f"{WEB_BASE}/ayuntamiento/ordenanzas-municipales/",
]

DEFAULT_TRAMITE_PAGES: list[tuple[str, str]] = [
    (f"{SEDE_BASE}/board", "Tablón de anuncios — sede electrónica"),
    (f"{SEDE_BASE}/info", "Información pública — sede electrónica"),
    (f"{WEB_BASE}/sede-electronica/", "Sede electrónica — trámites y acceso"),
    (f"{WEB_BASE}/ayuntamiento/normas-urbanisticas/", "Normas urbanísticas municipales"),
]

RE_PREVIEW = re.compile(
    r'href="(https://cardenosa\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_ARTICLE = re.compile(
    r'href="(https://www\.cardenosa\.es/ayuntamiento/[^"\']+\.html)"',
    re.I,
)
RE_PDF = re.compile(
    r'href="(https://www\.cardenosa\.es/docus/[^"\']+\.pdf[^"\']*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|cartel.*licencia|modelo.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|reurbaniz|urbanizaci[oó]n|"
    r"uso excepcional|suelo r[uú]stico|instrumento|memoria|planos|bocyl|"
    r"subasta.*solar|enajenaci[oó]n.*solar|cat[aá]logo|ordenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|proceso selectivo|pleno|"
    r"plusvalia|basura|residuos|vehiculos|notificaci[oó]n expediente|igualdad|"
    r"jurado|juez de paz|pe[oó]n|iae|cobranza|teletrabajo|calendario fiscal|"
    r"selecci[oó]n de personal|tribunal|convocatoria pleno|monitor actividades|"
    r"ivtm|tasa municipal|elecciones|quema|incendio|meteorol|bicicleta|"
    r"empleo p[uú]blico|alguacil|operario)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_YEAR = re.compile(r"/docus/ayuntamiento/(\d{4})/")


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    m = RE_DOC_YEAR.search(text or "")
    if m:
        return f"{m.group(1)}-01-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas urban" in n:
        return "normas urbanísticas"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "subasta" in n or "enajenaci" in n:
        return "subasta urbanística"
    if "cat[aá]logo" in n:
        return "catálogo urbanístico"
    if "planos" in n or "ordenaci" in n:
        return "planos planeamiento"
    if "modificaci" in n:
        return "modificación puntual"
    if "sector" in n:
        return "sector"
    return "urbanismo"


class CardenosaAyuntamientoAdapter(AyuntamientoAdapter):
    """Diputación de Ávila CMS + sede espublico + IDECyL WFS PLAU CyL."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.rss_url = str(self.config.get("rss_url") or RSS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.plau_url = str(
            self.config.get("plau_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=049"
        )
        raw_tramites = self.config.get("tramite_pages") or DEFAULT_TRAMITE_PAGES
        self.tramite_pages: list[tuple[str, str]] = []
        for item in raw_tramites:
            if isinstance(item, dict):
                self.tramite_pages.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.tramite_pages.append((str(item[0]), str(item[1])))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cardenosa/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            return resp.read().decode("utf-8", errors="replace")

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
                "count": "200",
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
                titulo = _strip_html(str(props.get("n_titulo") or ""))
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
                    "titulo": titulo[:500],
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
            if titulo and wfs_title and (titulo in wfs_title or wfs_title in titulo):
                for key in (
                    "geom_geojson",
                    "geometry_source",
                    "geometry_source_url",
                    "coord_source",
                    "lat",
                    "lon",
                ):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
                return
        for token in re.split(r"[\s,/()-]+", titulo):
            if len(token) < 5:
                continue
            for wfs_rec in self._collect_wfs_proyectos():
                wfs_title = str(wfs_rec.get("titulo") or "").lower()
                if token in wfs_title:
                    for key in (
                        "geom_geojson",
                        "geometry_source",
                        "geometry_source_url",
                        "coord_source",
                        "lat",
                        "lon",
                    ):
                        if wfs_rec.get(key) is not None:
                            rec[key] = wfs_rec[key]
                    return

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url, sede=True)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for rec in self._parse_board_table(html, origen):
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.rss_url)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            titulo = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            if not titulo or not url:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": _parse_rss_date(item.findtext("pubDate") or ""),
                    "origen": "rss",
                }
            )
        return rows

    def _collect_seed_articles(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_ARTICLE.finditer(html):
                url = m.group(1)
                if url in seen:
                    continue
                seen.add(url)
                titulo_m = re.search(
                    r'href="' + re.escape(url) + r'"[^>]*>.*?<h1>([^<]+)</h1>',
                    html,
                    re.S | re.I,
                )
                titulo = _strip_html(titulo_m.group(1)) if titulo_m else ""
                if not titulo:
                    slug = Path(urllib.parse.urlparse(url).path).stem
                    titulo = slug.replace("-", " ")
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(url),
                        "origen": "web_listing",
                    }
                )
        return rows

    def _collect_detail_pdfs(self, article_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(article_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        title_m = re.search(r"<h1>([^<]+)</h1>", html, re.I)
        page_title = _strip_html(title_m.group(1)) if title_m else ""
        date_m = re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)
        fecha = None
        if date_m:
            fecha = _parse_fecha_iso(date_m.group(1)[:10]) or _fecha_from_blob(date_m.group(1))
        for m in RE_PDF.finditer(html):
            pdf = m.group(1)
            name = unescape(urllib.parse.unquote(Path(pdf).stem)).replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "titulo": name[:500] or page_title,
                    "url": article_url,
                    "pdf_url": pdf,
                    "fecha": fecha or _fecha_from_blob(pdf),
                    "page_title": page_title,
                    "origen": "web_pdf",
                }
            )
        return rows

    @staticmethod
    def _parse_plau_rows(html: str, fallback_url: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c and c != "\xa0"]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            doc_m = (
                re.search(r"doGoBoletin\('(\d+)'", tr)
                or re.search(r"doOpen\('(\d+)'", tr)
                or re.search(r"openDocuIndice\.do[^\"']*cDocId=(\d+)", tr)
                or re.search(r"ldoc_files\.do[^\"']*cDocId=(\d+)", tr)
            )
            doc_id = doc_m.group(1) if doc_m else ""
            url = f"{PLAU_BASE}/openDocumento.do?cDocId={doc_id}" if doc_id else fallback_url
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": cells[2],
                    "instrumento": f"{cells[0]} {cells[1]}".strip(),
                    "doc_id": doc_id,
                    "origen": "plau_jcyl",
                }
            )
        return rows

    def _collect_plau(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.plau_url)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._parse_plau_rows(html, self.plau_url):
            key = (item.get("doc_id") or "") + item["title"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": item["title"][:500],
                    "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                    "url": item["url"],
                    "instrumento": item.get("instrumento") or "",
                    "origen": "plau_jcyl",
                }
            )
        return rows

    def _rss_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _article_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('page_title', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or f"{WEB_BASE}/ayuntamiento/normas-urbanisticas/",
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _plau_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('instrumento', '')}"
        if not RE_PROYECTO.search(blob) and "plau" not in blob.lower():
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "instrumento": row.get("instrumento"),
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
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
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo in self.tramite_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "tramite_info",
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
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_info"),
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

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for item in self._collect_plau():
            add(self._plau_to_proyecto(item))
        articles = self._collect_seed_articles()
        for item in articles:
            add(self._article_to_proyecto(item))
            for pdf_row in self._collect_detail_pdfs(item["url"]):
                add(self._pdf_to_proyecto(pdf_row))
        for item in self._collect_rss():
            add(self._rss_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau_jcyl": sum(1 for r in rows if r.get("origen") == "plau_jcyl"),
            "web_listing": sum(1 for r in rows if r.get("origen") == "web_listing"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
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
