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
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WP_BASE = "https://medinaderioseco.org"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://medinaderioseco.sedelectronica.es"
PLAI_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
MUNICIPIO = "Medina de Rioseco"
ID_PREFIX = "medina-de-rioseco"
PLAI_MUNICIPIO = 86
PLAI_PROVINCIA = 47

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo-y-vivienda/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-general-de-ordenacion-urbana/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-especial-del-casco-historico/",
    f"{WP_BASE}/urbanismo-y-vivienda/aru-medina-de-rioseco/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-de-concentracion-parcelaria/",
    f"{WP_BASE}/urbanismo-y-vivienda/proyecto-de-normalizacion-de-fincas-y-proyecto-de-urbanizacion-de-viales-de-la-unidad-aa-12-del-pgou-medina-de-rioseco/",
    f"{WP_BASE}/modelos-de-formularios-y-solicitudes/",
    f"{WP_BASE}/informacion-publica-relativa-al-ajuste-de-alineaciones-de-viario-en-las-calles-ancha-macio-prado-y-ahogaznos/",
    f"{WP_BASE}/informacion-publica-aprobacion-definitiva-proyecto-de-urbanizacion-de-la-travesia-de-la-carretera-a-villaesper/",
]

RE_PREVIEW = re.compile(
    r'href="(https://medinaderioseco\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|cartel.*licencia|modelo.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pech|aru|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto de (?:urbaniz|actuaci|normaliz)|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|actuaci[oó]n urban|sector|"
    r"concentraci[oó]n parcelaria|expropiaci[oó]n|normalizaci[oó]n|bocyl|surd|sued|"
    r"unidad de (?:ejecuci[oó]n|actuaci)|pol[ií]gono industrial)",
)
RE_WP_EXCLUDE = re.compile(
    r"(?i)(fiestas|cine|empleo|concurso|deporte|navidad|verano cultural|"
    r"ciberseguridad|coworking|sorteo|elecciones|constituci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleo p[uú]blico|proceso selectivo|"
    r"pleno ordinario|subvenci[oó]n deportiv|matrimonio|carnaval|tribut|iae|"
    r"notificaci[oó]n colectiva|auxiliar biblioteca|puntuaciones provisionales)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents|download)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?medinaderioseco\.org)?/(?:wp-content/uploads|download)/[^"\']+\.(?:pdf|PDF)[^"\']*)["\']',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"SU[-\s]?RD[-\s]?SI[-\s]?\d+|SURD[-\s]?SI[-\s]?\d+|"
    r"SU[-\s]?ED[-\s]?I\d+|SUED[-\s]?I\d+|"
    r"AA[-\s]?\d+|"
    r"SUR[-\s]?D\s*(?:SR|SA|SI|I)[-\s]?\d+|"
    r"SU[-\s]?NC\s*(?:ST|SR)[-\s]?\d+|"
    r"SUED[-\s]?A\d+|"
    r"SECTOR\s+[A-Z0-9][\w\s-]{1,30}"
    r")\b",
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


def _parse_fecha_iso(text: str) -> str | None:
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", text or "")
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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = code.replace("SURDSI", "SUR-D SI-").replace("SURD SI", "SUR-D SI-")
    code = re.sub(r"SUR[-\s]?D\s*SI[-\s]?(\d+)", r"SUR-D SI-\1", code)
    code = re.sub(r"SU[-\s]?ED[-\s]?I(\d+)", r"SUED-I\1", code)
    code = re.sub(r"AA[-\s]?(\d+)", r"AA-\1", code)
    return code


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "ppi" in n:
        return "plan parcial"
    if "pech" in n or "casco hist" in n:
        return "PECH"
    if "aru" in n or "regeneraci" in n:
        return "ARU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "normalizaci" in n:
        return "normalización fincas"
    if "urbanizaci" in n:
        return "proyecto urbanización"
    if "concentraci" in n and "parcel" in n:
        return "concentración parcelaria"
    if "expropiaci" in n:
        return "expropiación"
    if "modificaci" in n:
        return "modificación puntual"
    if "sector" in n or "surd" in n or "sued" in n:
        return "sector urbanístico"
    return "urbanismo"


class MedinaDeRiosecoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + sede espublico + PLAI JCYL + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self.plai_municipio = int(self.config.get("plai_municipio") or PLAI_MUNICIPIO)
        self.plai_provincia = int(self.config.get("plai_provincia") or PLAI_PROVINCIA)
        self.plai_max_pages = int(self.config.get("plai_max_pages", 8))
        self.plai_page_size = int(self.config.get("plai_page_size", 15))
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
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-medina-de-rioseco/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _wfs_query_url(self, layer: str, *, cql: str | None = None) -> str:
        params: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": layer,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": "200",
            "CQL_FILTER": cql or f"n_mun = '{self.wfs_municipio}'",
        }
        return f"{self.wfs_base}?{urllib.parse.urlencode(params)}"

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
                    "sector_code": props.get("n_num_sect"),
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

    def _wfs_sector_geometry(self, sector_code: str) -> tuple[dict[str, Any] | None, str | None]:
        if sector_code in self._sector_geom_cache:
            hit = self._sector_geom_cache[sector_code]
            if hit:
                return hit["geom_geojson"], hit["geometry_source_url"]
            return None, None

        safe_mun = self.wfs_municipio.replace("'", "''")
        variants = [sector_code, sector_code.replace("-", " "), sector_code.replace(" ", "-")]
        geom: dict[str, Any] | None = None
        source_url: str | None = None
        for variant in dict.fromkeys(variants):
            safe_code = variant.replace("'", "''")
            cql = f"n_mun='{safe_mun}' AND n_num_sect ILIKE '%{safe_code}%'"
            url = self._wfs_query_url("urbanismo:plau_cyl_sectores", cql=cql)
            try:
                data = self._fetch_json(url)
                feats = data.get("features") or []
                if feats and isinstance(feats[0], dict):
                    geom = feats[0].get("geometry")
                    source_url = url
                    if isinstance(geom, dict) and geom.get("type"):
                        break
            except (urllib.error.URLError, json.JSONDecodeError):
                continue

        if isinstance(geom, dict) and geom.get("type"):
            self._sector_geom_cache[sector_code] = {
                "geom_geojson": geom,
                "geometry_source_url": source_url,
            }
            return geom, source_url
        self._sector_geom_cache[sector_code] = None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "url", "sector_code"))
        for code in _sector_codes_from_text(blob):
            geom, source_url = self._wfs_sector_geometry(code)
            if not geom:
                continue
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = source_url
            rec["coord_source"] = "portal_geometry_centroid"
            rec["sector_code"] = code
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
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
                    "sector_code",
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

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info", "info_tablon")):
            try:
                html = self._fetch(url, sede=True)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _plai_page_url(self, offset: int) -> str:
        params = {
            "pager.size": str(self.plai_page_size),
            "pager.reload": "no",
            "municipio": f"{self.plai_municipio:03d}",
            "provincia": str(self.plai_provincia),
            "urlResults": "searchVPubDocMuniPlai.do",
            "pager.offset": str(offset),
        }
        return f"{PLAI_BASE}/searchVPubDocMuniPlai.do?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_plai_rows(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            fecha_pub = cells[2]
            doc_m = re.search(r"doOpen\('(\d+)'", tr) or re.search(r"doOpenDocumento\((\d+)\)", tr)
            boletin_m = re.search(r"doGoBoletin\('(\d+)'", tr)
            doc_id = doc_m.group(1) if doc_m else (boletin_m.group(1) if boletin_m else None)
            if doc_id and doc_m:
                url = f"{PLAI_BASE}/openDocumento.do?cDocId={doc_id}"
            elif boletin_m:
                url = f"{PLAI_BASE}/openBoletin.do?cDocId={boletin_m.group(1)}"
            else:
                url = (
                    f"{PLAI_BASE}/searchVPubDocMuniPlai.do?"
                    f"provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}"
                )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": fecha_pub,
                    "instrumento": cells[1] if len(cells) > 1 else "",
                    "origen": "plai_jcyl",
                    "doc_id": doc_id or "",
                }
            )
        return rows

    def _collect_plai(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(self.plai_max_pages):
            offset = page * self.plai_page_size
            try:
                html = self._fetch(self._plai_page_url(offset))
            except urllib.error.URLError:
                break
            parsed = self._parse_plai_rows(html)
            if not parsed:
                break
            for item in parsed:
                key = item["url"] + item["title"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": item["title"][:500],
                        "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                        "url": item["url"],
                        "instrumento": item.get("instrumento") or "",
                        "origen": "plai_jcyl",
                    }
                )
            if len(parsed) < self.plai_page_size:
                break
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<title>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                link_text = ""
                ctx = html[max(0, m.start() - 200) : m.end() + 50]
                text_m = re.search(r">([^<]{3,120})</a>", ctx)
                if text_m:
                    link_text = _strip_html(text_m.group(1))
                titulo = link_text or name
                blob = f"{page_title} {titulo} {pdf}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "urban" not in page_url.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_blob(pdf + " " + titulo),
                        "origen": "wp_pdf",
                        "page_title": page_title,
                    }
                )
        return rows

    def _paginate_wp(self, endpoint: str, max_pages: int = 5) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page_num in range(1, max_pages + 1):
            url = f"{WP_API}/{endpoint}?per_page=100&page={page_num}&status=publish"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def _wp_item_to_proyecto(self, item: dict[str, Any], origen: str) -> dict[str, Any] | None:
        title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        content = str((item.get("content") or {}).get("rendered") or "")
        blob = f"{title} {_strip_html(content)}"
        if not RE_PROYECTO.search(blob):
            return None
        url = str(item.get("link") or "").strip()
        if not url:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _iso_date_wp(str(item.get("date") or item.get("modified") or "")),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        self._attach_geometry(rec)
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
            "url": row.get("url") or row.get("pdf_url") or f"{WP_BASE}/urbanismo-y-vivienda/",
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _plai_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('instrumento', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "instrumento": row.get("instrumento") or None,
        }
        self._attach_geometry(rec)
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (self.board_url, "tablón de anuncios — licencias y urbanismo"),
            (f"{WP_BASE}/modelos-de-formularios-y-solicitudes/", "modelos y formularios urbanismo"),
            (f"{WP_BASE}/urbanismo-y-vivienda/", "urbanismo y vivienda — trámites"),
            (f"{self.sede_base}/catalog", "catálogo trámites sede electrónica"),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo in pages:
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
                    "origen": "wp_tramite",
                }
            )
        return rows

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
        if row.get("categoria", "").lower() in ("urbanismo", "ordenanzas y reglamentos"):
            pass
        elif not RE_PROYECTO.search(blob):
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
        self._attach_geometry(rec)
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
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
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

        for page in self._paginate_wp("pages"):
            add(self._wp_item_to_proyecto(page, "wp_pages"))
        for post in self._paginate_wp("posts", max_pages=10):
            add(self._wp_item_to_proyecto(post, "wp_posts"))
        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_plai():
            add(self._plai_to_proyecto(item))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_pages": sum(1 for r in rows if r.get("origen") == "wp_pages"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "wp_pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "plai": sum(1 for r in rows if r.get("origen") == "plai_jcyl"),
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
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
