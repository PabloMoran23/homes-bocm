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

WEB_BASE = "https://www.aytogalende.net"
SEDE_BASE = "https://galende.sedelectronica.es"
PLANPUBLICA_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"
MUNICIPIO = "Galende"
ID_PREFIX = "galende"
WFS_C_MUN = "49085"
PLAN_PROVINCIA = "49"
PLAN_MUNICIPIO = "85"
URBANISMO_CATEGORY = f"{WEB_BASE}/index.php/tablon-de-anuncios/category/3-urbanismo"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_URLS: list[tuple[str, str]] = [
    (
        f"{PLANPUBLICA_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={PLAN_PROVINCIA}&municipio={PLAN_MUNICIPIO}",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
    (
        f"{PLANPUBLICA_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={PLAN_PROVINCIA}&municipio={PLAN_MUNICIPIO}",
        "Planeamiento urbanístico en información pública (Junta CYL)",
    ),
    (URBANISMO_CATEGORY, "Tablón urbanismo (jDownloads)"),
]

RE_PREVIEW = re.compile(
    r'href="((?:https://galende\.sedelectronica\.es)?/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://galende\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_JDOWNLOAD = re.compile(
    r'<b><a href="(/index\.php/tablon-de-anuncios/(?:download|summary)/3-urbanismo/[^"]+)">([^<]+)</a></b>',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|certificado.*urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|normas urban|delimitaci[oó]n|"
    r"unidad(?:es)? de ejecuci[oó]n|suelo urbano|su[- ]?nc|s\.u\.n\.c|"
    r"ausr|autorizaci[oó]n de uso|uso excepcional|rehabilitaci[oó]n|vut\b|"
    r"pol[ií]gono|parcela|expdte|exte\b)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"ED\.?\s*VIG\.?\s*[\w.]+|"
    r"POL\.?\s*\d+|"
    r"SU[- ]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+(?:[-/]\d+)?|"
    r"SECTOR\s+[A-Z0-9.-]+|"
    r"\bNUM\b"
    r")\b",
)
RE_EXPDTE = re.compile(r"(?i)(?:expdte\.?|exte\.?|expediente)\s*[:\.]?\s*(\d+/\d{4})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    expte = RE_EXPDTE.search(text or "")
    if expte:
        year = expte.group(1).split("/")[-1]
        if year.isdigit():
            return f"{year}-01-01"
    years = re.findall(r"\b((?:19|20)\d{2})\b", text or "")
    if years:
        return f"{max(int(y) for y in years)}-01-01"
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "", code)
    code = re.sub(r"ED\.VIG\.", "ED.vig.", code, flags=re.I)
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


def _proyecto_tipo(text: str) -> str:
    t = text.lower()
    if "estudio de detalle" in t:
        return "estudio de detalle"
    if "autorizaci" in t and "uso excepcional" in t:
        return "autorización uso excepcional"
    if "ausr" in t:
        return "autorización uso suelo rústico"
    if "modificaci" in t and "normas urban" in t:
        return "modificación normas urbanísticas"
    if "modificaci" in t:
        return "modificación planeamiento"
    if "informaci" in t and "p" in t and "blica" in t:
        return "información pública"
    if "rehabilitaci" in t:
        return "rehabilitación"
    if "pgou" in t or "plan general" in t or "num" in t:
        return "normas urbanísticas"
    if "sector" in t or re.search(r"ed\.vig", t):
        return "sector urbanístico"
    if "planeamiento" in t:
        return "planeamiento"
    return "urbanismo"


class GalendeAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla jDownloads + sede espublico + PlanPublica JCyL + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info.0")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier.0")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_CATEGORY)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_c_mun = str(self.config.get("wfs_c_mun") or WFS_C_MUN)
        self.plan_provincia = str(self.config.get("plan_provincia") or PLAN_PROVINCIA)
        self.plan_municipio = str(self.config.get("plan_municipio") or PLAN_MUNICIPIO)
        self.seed_urls = list(self.config.get("seed_urls") or DEFAULT_SEED_URLS)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-galende/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r'<tbody[^>]*id="[^"]*">(.*?)</tbody>', html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                r'href="((?:https://galende\.sedelectronica\.es)?/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            url = link_m.group(1) if link_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            text_m = re.search(rf'href="{re.escape(m.group(1))}"[^>]*>([^<]+)<', local, re.I)
            titulo = ""
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            rows.append(
                {
                    "titulo": (titulo or url)[:500],
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
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url, sede=True)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites_catalog(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, sede=True)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_jdownloads_urbanismo(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        start = 0
        while True:
            page_url = self.urbanismo_url if start == 0 else f"{self.urbanismo_url}?start={start}"
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError, ConnectionError):
                break
            found = 0
            for m in RE_JDOWNLOAD.finditer(html):
                href, titulo = m.group(1), _strip_html(m.group(2))
                url = href if href.startswith("http") else f"{self.web_base}{href}"
                url = re.sub(r"/summary/", "/download/", url)
                expte_m = RE_EXPDTE.search(titulo)
                by_url[url] = {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "expte": expte_m.group(1) if expte_m else None,
                    "origen": "jdownloads_urbanismo",
                }
                found += 1
            next_start = start + 8
            next_m = re.search(
                rf'category/3-urbanismo\?start={next_start}',
                html,
            )
            if not next_m or found == 0:
                break
            start = next_start
        return list(by_url.values())

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, fallback_title in self.seed_urls:
            if url == self.urbanismo_url:
                continue
            titulo = fallback_title
            try:
                html = self._fetch(url)
                title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
                if title_m:
                    titulo = _strip_html(title_m.group(1))
                    titulo = re.sub(r"\s*-\s*PLAU.*$", "", titulo, flags=re.I).strip()
            except (urllib.error.URLError, OSError, ConnectionError):
                pass
            rows.append(
                {
                    "titulo": (titulo or fallback_title)[:500],
                    "url": url,
                    "origen": "jcyl_planeamiento",
                }
            )
        return rows

    def _parse_planpublica_rows(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 4 or cells[0] in {"Libro", "Tipo", "FIGURAS"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            instrumento = cells[1] if len(cells) > 1 else ""
            fecha = _parse_fecha_dmy(cells[2]) if len(cells) > 2 else None
            doc_m = re.search(r"doOpenDocumento\((\d+)\)", tr) or re.search(
                r"doGoBoletin\('(\d+)'", tr
            )
            doc_id = doc_m.group(1) if doc_m else None
            url = (
                f"{PLANPUBLICA_BASE}/openDocumento.do?cDocId={doc_id}"
                if doc_id
                else f"{PLANPUBLICA_BASE}/searchVPubDocMuniPlau.do?provincia={self.plan_provincia}&municipio={self.plan_municipio}"
            )
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "instrumento": instrumento,
                    "origen": origen,
                }
            )
        return rows

    def _collect_planpublica(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        urls = (
            (
                f"{PLANPUBLICA_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={self.plan_provincia}&municipio={self.plan_municipio}",
                "planpublica_plau",
            ),
            (
                f"{PLANPUBLICA_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={self.plan_provincia}&municipio={self.plan_municipio}",
                "planpublica_plai",
            ),
        )
        for url, origen in urls:
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for rec in self._parse_planpublica_rows(html, origen):
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": f"c_mun='{self.wfs_c_mun}'",
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
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("n_sector") or "").strip()
                num = str(props.get("n_num_sect") or "").strip()
                titulo = sector or num
                if sector and num and sector != num:
                    titulo = f"{sector} ({num})"
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("n_instrum") or props.get("c_instrum") or "")
                blob = f"{titulo} {instrum}"
                fecha = None
                for fk in ("f_bocyl", "f_aprob"):
                    raw = str(props.get(fk) or "")
                    if raw and len(raw) >= 10:
                        fecha = raw[:10]
                        break
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
                if num:
                    rec["sector_code"] = _normalize_sector_code(num)
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                    if num:
                        self._sector_geom_cache[_normalize_sector_code(num)] = {
                            "geom_geojson": geom,
                            "geometry_source_url": url,
                        }
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _wfs_sector_geometry(self, sector_code: str) -> tuple[dict[str, Any] | None, str | None]:
        norm = _normalize_sector_code(sector_code)
        if norm in self._sector_geom_cache:
            hit = self._sector_geom_cache[norm]
            if hit:
                return hit["geom_geojson"], hit["geometry_source_url"]
            return None, None
        escaped = norm.replace("'", "''")
        cql = f"c_mun='{self.wfs_c_mun}' AND n_num_sect ILIKE '%{escaped}%'"
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "urbanismo:plau_cyl_sectores",
                "count": "1",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_base}?{qs}"
        geom: dict[str, Any] | None = None
        try:
            data = self._fetch_json(url)
            feats = data.get("features") or []
            if feats and isinstance(feats[0], dict):
                geom = feats[0].get("geometry")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, OSError):
            geom = None
        if isinstance(geom, dict) and geom.get("type"):
            self._sector_geom_cache[norm] = {"geom_geojson": geom, "geometry_source_url": url}
            return geom, url
        self._sector_geom_cache[norm] = None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "expte", "sector_code", "instrumento"))
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

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
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

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if row.get("origen") == "jdownloads_urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n|estudio de detalle|ausr|autorizaci[oó]n de uso",
            blob,
        ):
            return None
        key = row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("instrumento"):
            rec["instrumento"] = row["instrumento"]
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites_catalog():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites_catalog():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for item in self._collect_planpublica():
            add(self._generic_to_proyecto(item))
        for item in self._collect_jdownloads_urbanismo():
            add(self._generic_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites_catalog():
            add(self._generic_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "jdownloads": sum(1 for r in rows if r.get("origen") == "jdownloads_urbanismo"),
            "planpublica": sum(1 for r in rows if str(r.get("origen", "")).startswith("planpublica")),
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
