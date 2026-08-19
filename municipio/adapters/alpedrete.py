from __future__ import annotations

import hashlib
import json
import re
import ssl
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

WP_BASE = "https://www.alpedrete.es"
SEDE_BASE = "https://carpeta.alpedrete.es/eAdmin"
MUNICIPIO = "Alpedrete"
ID_PREFIX = "alpedrete"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
RSS_FEED = f"{WP_BASE}/informacion-cat/urbanismo-y-obras/feed/"
IMPRESOS_URL = f"{WP_BASE}/portal-de-tramites/impresos/"
URBANISMO_CAT = f"{WP_BASE}/informacion-cat/urbanismo-y-obras/"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "ALPEDRETE"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/aprobacion-inicial-plan-general-de-ordenacion-urbana/",
    f"{WP_BASE}/el-pgou-de-alpedrete-un-paso-mas-cerca-tras-la-aprobacion-de-la-resolucion-de-alegaciones-en-el-pleno/",
    URBANISMO_CAT,
]

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLANEAMIENTO",
    "PGOU",
    "UA-",
    "SR-",
    "BOCM",
    "OBRA",
    "APROBACION",
)

DEFAULT_IMPRESOS_SLUGS: list[str] = [
    "documentacion-licencia-de-obras",
    "declaracion-responsable-urbanistica",
    "declaracion-responsable-urbanistica-inicio-de-obra",
    "declaracion-responsable-urbanistica-primera-ocupacion",
    "documentacion-licencia-primera-ocupacion",
    "documentacion-obra-mayor",
    "documentacion-especifica-declaracion-responsable-sin-proyecto-loe",
    "documentacion-licencia-tala-de-arbolado",
    "autorizacion-de-representacion-urbanismo",
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)(?:EXP\.?\s*)?([0-9]+[-/][0-9]+/[0-9]{4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|obra|tala)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"primera ocupaci[oó]n|inicio de obra|obra mayor|autorizaci[oó]n.*urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental)|ua-\d|sr-\d|bocm|"
    r"proyecto de|memoria|planos|alegacion|normas subsidiarias|nnss)",
)
RE_SKIP = re.compile(
    r"(?i)(presupuesto|modificaci[oó]n presupuestaria|residuos s[oó]lidos|punto limpio|"
    r"contrataci[oó]n servicio|mesa permanente|iae\b|padr[oó]n|igualdad|"
    r"corte[s]? (?:de )?(?:agua|luz|el[eé]ctric)|suministro el[eé]ctrico|asfaltado|parque|"
    r"piscina[s]?|pir\b|pueblos con vida|infraestructur)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UA|SR|UE|AD|AN|AI|PAU|S)-[\w.\-/]+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.alpedrete\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_DOWNLOAD_HREF = re.compile(
    r'href="(https://www\.alpedrete\.es/download/[^"]+)"',
    re.I,
)
RE_RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
RE_RSS_TITLE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.S)
RE_RSS_LINK = re.compile(r"<link>(.*?)</link>")
RE_RSS_DATE = re.compile(r"<pubDate>(.*?)</pubDate>")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    try:
        dt = datetime.strptime(text.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name.replace("-", " "))


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if re.search(r"\bua-\d|\bsr-\d", n):
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "nnss" in n or "normas subsidiarias" in n or "pgou" in n:
        return "planeamiento"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "aprobaci" in n:
        return "aprobación"
    if "bocm" in n:
        return "publicación BOCM"
    return default


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " alpedrete"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


class AlpedreteAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + eAdmin sede (tablón) + impresos trámites + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.impresos_slugs = list(self.config.get("impresos_slugs") or DEFAULT_IMPRESOS_SLUGS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-alpedrete/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        ctx = self._ssl_ctx if "carpeta.alpedrete.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or (
                "iso-8859-1" if "carpeta.alpedrete.es" in url else "utf-8"
            )
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.wp_base + "/", href)

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title or RE_SKIP.search(title):
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_token)
            by_id[ann_id] = rec
        return by_id

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
            html = self._fetch(TABLON_ALL)
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_rss_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml = self._fetch(RSS_FEED)
        except urllib.error.URLError:
            return rows
        for item in RE_RSS_ITEM.findall(xml):
            title_m = RE_RSS_TITLE.search(item)
            link_m = RE_RSS_LINK.search(item)
            date_m = RE_RSS_DATE.search(item)
            if not title_m or not link_m:
                continue
            title = _clean_title(title_m.group(1))
            link = link_m.group(1).strip()
            if RE_SKIP.search(title):
                continue
            if not RE_PROYECTO.search(title):
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", link),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": _parse_rss_date(date_m.group(1)) if date_m else _parse_fecha_dmy(title),
                "tipo": _proyecto_tipo(title),
                "url": link,
                "source": "ayuntamiento",
                "origen": "wp_rss",
            }
            try:
                page_html = self._fetch(link)
                pdf_m = RE_PDF_HREF.search(page_html)
                if pdf_m:
                    rec["pdf_url"] = self._abs_url(pdf_m.group(1))
                    rec["fecha"] = rec.get("fecha") or _fecha_from_url(rec["pdf_url"])
            except urllib.error.URLError:
                pass
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _extract_seed_proyectos(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = self._abs_url(m.group(1), page_url)
            if pdf_url in seen:
                continue
            name = Path(pdf_url).name
            blob = f"{name} {pdf_url}".lower()
            if not any(k in blob for k in ("bocm", "pgou", "urban", "planeam", "informaci", "alegacion")):
                continue
            title = re.sub(r"[-_.]+", " ", name.replace(".pdf", ""))[:500]
            seen.add(pdf_url)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf_url),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": _parse_fecha_dmy(title) or _fecha_from_url(pdf_url),
                "tipo": _proyecto_tipo(title),
                "url": page_url,
                "pdf_url": pdf_url,
                "source": "ayuntamiento",
                "origen": "wp_pdf",
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._extract_seed_proyectos(html, page_url))
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": cql,
            "count": str(count),
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        return list((data or {}).get("features") or [])

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=250)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache[name.upper()] = f
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache[code_m.group(1).upper()] = f
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper()
            feat = cache.get(code)
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
                count=10,
            )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
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
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=250)
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
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

    def _collect_impresos_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(IMPRESOS_URL)
        except urllib.error.URLError:
            html = ""
        for m in RE_DOWNLOAD_HREF.finditer(html):
            url = m.group(1).split("?")[0]
            slug = url.rstrip("/").split("/")[-1]
            if slug not in self.impresos_slugs and not RE_LICENCIA.search(slug.replace("-", " ")):
                continue
            if url in seen:
                continue
            seen.add(url)
            title = slug.replace("-", " ").replace(":", " ")
            title = title[:1].upper() + title[1:]
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo; no concesión publicada",
                    "origen": "impresos_wp",
                }
            )
        for slug in self.impresos_slugs:
            url = f"{self.wp_base}/download/{slug}/"
            if url in seen:
                continue
            seen.add(url)
            title = slug.replace("-", " ")
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:1].upper() + title[1:],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo; no concesión publicada",
                    "origen": "impresos_wp",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", TABLON_ALL),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": TABLON_ALL,
                "source": "ayuntamiento",
                "nota": "Anuncios y edictos publicados en sede eAdmin",
                "origen": "sede_tablon",
            }
        )
        return rows

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_SKIP.search(title):
            return None
        if not RE_LICENCIA.search(title):
            return None
        if RE_PROYECTO.search(title) and not re.search(r"(?i)licencia", title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|declaraci[oó]n responsable)", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _title_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_SKIP.search(title):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        self._enrich_geometry(out)
        return out

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
        tablon = self._collect_tablon()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_impresos_licencias():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_impresos_licencias():
            existing[rec["id"]] = rec
        tablon = self._collect_tablon()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_rss_posts():
            add(rec)
        for rec in self._collect_seed_pages():
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        sit_n = sum(1 for r in rows if r.get("origen") == "sit_wfs")
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sit_n,
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
