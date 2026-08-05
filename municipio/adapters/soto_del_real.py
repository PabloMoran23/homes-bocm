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
from municipio.gis.sitcm import WFS_BASE, resolve_municipio_wfs

WP_BASE = "https://www.ayto-sotodelreal.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://sedesotodelreal.eadministracion.es/eAdmin"
MUNICIPIO = "Soto del Real"
ID_PREFIX = "soto-del-real"

DEFAULT_WP_SEED_PAGES: list[str] = [
    f"{WP_BASE}/planeamiento-urbanistico/",
    f"{WP_BASE}/planos-de-ordenacion/",
    f"{WP_BASE}/plan-sostenible-de-ordenacion-urbana/",
    f"{WP_BASE}/urbanismo-y-licencias/",
    f"{WP_BASE}/urbanismo-y-obras-publicas/",
    f"{WP_BASE}/recepcion-de-urbanizaciones-2/",
    f"{WP_BASE}/licencias-y-declaraciones-responsables/",
    f"{WP_BASE}/urbanismo-y-licencias/solicitud-actividades/",
]

TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TABLON_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLAN",
    "PGOU",
    "PSOU",
    "AVANCE",
    "UA-",
    "APROBACION",
    "CONVENIO",
    "REPARCEL",
    "EDICTO",
)

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)EXP\.?\s*([0-9]+/[0-9]{4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|actividad|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|inspecci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|sostenible)|pgou|psou|nnss|"
    r"normas subsidiarias|informaci[oó]n p[uú]blica|expediente|reparcel|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|modificaci[oó]n puntual|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|hidrol)|ua-\d|ia-\d|sau-|ue-\d|"
    r"avance|calificaci[oó]n|ordenaci[oó]n|recepci[oó]n de urbaniz|urbanizaci[oó]n|"
    r"memoria de (?:informaci[oó]n|ordenaci[oó]n)|plano.*orden|bocm)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|igualdad|notificaci[oó]n telem|"
    r"campamento urbano|campamentos urbanos|arte urbano|valor-art|urban sport|"
    r"asfaltado|peatonal|videovigilancia|aparcamiento|residuos s[oó]lidos urbanos|"
    r"subvenci[oó]n.*estudio|ayudas.*estudio|convenio.*escuela|convenio.*unie|"
    r"convenio.*zombie|convenio.*piscina|pliego.*residuos|jazz l[ií]rico|"
    r"bosque urbano|corredor verde|fiestas patronales)",
)
RE_WP_EXCLUDE = RE_EXCLUDE
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UA|IA|SAU|UE|AD|AN|AI|PAU|S)-[\w\d.\-]+)\b")
RE_WP_PDF = re.compile(
    r'href="((?:https://www\.ayto-sotodelreal\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _doc_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if "psou" in n or "plan sostenible" in n:
        return "PSOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if re.search(r"\bua-\d", n):
        return "unidad de actuación"
    if re.search(r"\bia-\d", n):
        return "instalación aislada"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "avance" in n:
        return "avance planeamiento"
    if "memoria" in n:
        return "memoria"
    if "plano" in n or "ordenaci" in n or "calificaci" in n:
        return "planeamiento"
    if "recepci" in n and "urbaniz" in n:
        return "recepción urbanización"
    return default


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de soto", " soto del real"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    skip = {"soto", "real", "general", "avance", "documento", "memoria", "plano"}
    for p in parts:
        k = p.lower()
        if k not in seen and k not in skip and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:8]


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


class SotoDelRealAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (planeamiento + noticias) + sede eAdmin (tablón) + SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api_base") or f"{self.wp_base}/wp-json/wp/v2").rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.wp_seed_pages = [str(u) for u in (self.config.get("wp_seed_pages") or DEFAULT_WP_SEED_PAGES)]
        self.search_terms = list(self.config.get("tablon_search_terms") or TABLON_SEARCH_TERMS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_municipio = str(
            geom_cfg.get("municipio_filter")
            or resolve_municipio_wfs(MUNICIPIO)
            or "SOTO DEL REAL"
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-soto-del-real/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href).replace("&amp;", "&"))

    def _extract_pdfs(self, html: str) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            url = self._abs_wp(m.group(1))
            if "dropbox.com" in url or url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url.split("?")[0]).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
            out.append((name[:500], url, _clean_title(name)))
        return out

    def _collect_seed_docs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        for page_url in self.wp_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for raw_name, pdf_url, titulo in self._extract_pdfs(html):
                blob = f"{titulo} {pdf_url}"
                if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    licencias.append(
                        {
                            "id": _stable_id("lic", pdf_url),
                            "fecha_concesion": _parse_fecha_dmy(pdf_url),
                            "tipo": titulo[:120],
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": titulo,
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "source": "ayuntamiento",
                            "origen": "formulario_wp",
                            "nota": "Formulario/modelo; no concesión publicada",
                        }
                    )
                elif RE_PROYECTO.search(blob) and not RE_EXCLUDE.search(blob):
                    rec: dict[str, Any] = {
                        "id": _stable_id("proy", pdf_url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha_dmy(pdf_url),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": "planeamiento_wp",
                    }
                    self._enrich_geometry(rec)
                    proyectos.append(rec)
        return proyectos, licencias

    def _paginate_wp_posts(self, max_pages: int = 12) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            url = f"{self.wp_api}/posts?per_page=100&page={page}&status=publish"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            posts.extend(batch)
            if len(batch) < 100:
                break
        return posts

    def _post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = _clean_title(str((post.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        fecha = None
        raw_date = str(post.get("date") or "")
        if raw_date:
            fecha = raw_date[:10]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": fecha,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": "wp_posts",
        }
        content = str((post.get("content") or {}).get("rendered") or "")
        pdfs = [self._abs_wp(m.group(1)) for m in RE_WP_PDF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        self._enrich_geometry(rec)
        return rec

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for post in self._paginate_wp_posts():
            rec = self._post_to_proyecto(post)
            if rec:
                rows.append(rec)
        return rows

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _doc_url(self.sede_base, doc_token)
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(self.tablon_url, data=body)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(self.tablon_url)
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.wp_base}/urbanismo-y-licencias/", "Urbanismo y licencias"),
            (f"{self.wp_base}/licencias-y-declaraciones-responsables/", "Licencias y declaraciones responsables"),
            (f"{self.wp_base}/urbanismo-y-licencias/solicitud-actividades/", "Solicitud licencia actividades"),
            (f"{self.sede_base.replace('/eAdmin', '')}/", "Sede electrónica — trámites urbanismo"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; concesiones en tablón sede cuando se publiquen",
                    "origen": "info_tramite",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "sitcm:VPLA_V_AMBITO",
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
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

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
        merged = _merge_geometries(same_name or [candidates[0][2]])
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39)*2)}'"
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
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        planeamiento_url = f"{self.wp_base}/planeamiento-urbanistico/"
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
                "url": planeamiento_url,
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

    def _tablon_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(rec["titulo"]):
            return None
        return {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": rec["titulo"],
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
            **({"pdf_url": rec["pdf_url"]} if rec.get("pdf_url") else {}),
        }

    def _tablon_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_EXCLUDE.search(title):
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        _, seed_lic = self._collect_seed_docs()
        for rec in seed_lic:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon().values():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") == "info_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        seed_proy, _ = self._collect_seed_docs()
        for rec in seed_proy:
            add(rec)
        for rec in self._collect_wp_proyectos():
            add(rec)
        for item in self._collect_tablon().values():
            add(self._tablon_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planeamiento_wp": sum(1 for r in rows if r.get("origen") == "planeamiento_wp"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
