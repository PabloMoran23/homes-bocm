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

WEB_BASE = "https://saldana.es"
SEDE_BASE = "https://saldana.sedelectronica.es"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
MUNICIPIO = "Saldaña"
ID_PREFIX = "saldana"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"
PLAU_PROVINCIA = 34
PLAU_MUNICIPIO = 157

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "planeamiento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_URLS: list[tuple[str, str]] = [
    (f"{WEB_BASE}/project/urbanismo/", "Urbanismo municipal — NUM y documentación"),
    (f"{WEB_BASE}/project/documentacion-oficial/", "Documentación oficial — modelos licencias"),
    (
        f"{PLAU_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={PLAU_PROVINCIA}&municipio={PLAU_MUNICIPIO}",
        "Planeamiento en información pública (Junta CYL)",
    ),
    (
        f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={PLAU_PROVINCIA}&municipio={PLAU_MUNICIPIO}",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
]

RE_PREVIEW = re.compile(
    r'href="(https://saldana\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://saldana\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|recepci[oó]n de obra|modelo.*licencia|licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|num\b|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|"
    r"sector|edicto|actuaci[oó]n urban|pol[ií]gono industrial|instrumento|"
    r"unidad(?:es)? de (?:actuaci[oó]n|ejecuci[oó]n)|suelo urban|"
    r"\b(?:SU[-\s]?NC|SUR)[-\s]?\d+)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"S\.?\s*U\.?\s*\.?\s*N\.?\s*C\.?\s*[-.]?\s*\d{1,2}|"
    r"SU[-\s]?NC[-\s]?\d{1,2}|"
    r"S\.?\s*U\.?\s*\.?\s*R\.?\s*[-.]?\s*\d{1,2}|"
    r"SUR[-\s]?\d{1,2}|"
    r"Sector\s+\d{1,2}"
    r")\b",
)
RE_PLAU_DOC = re.compile(
    r"doGoBoletin\('(\d+)',\s*'([^']+)'\)",
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?saldana\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = re.sub(r"SECTOR\s+", "Sector ", code, flags=re.I)
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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "normas urban" in n or re.search(r"\bnum\b", n):
        return "normas urbanísticas"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "polígono industrial" in n or "poligono industrial" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "sector" in n or re.search(r"\b(?:su-nc|sur)\b", n):
        return "sector urbanístico"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


def _plau_doc_url(cdoc_id: str) -> str:
    return f"{PLAU_BASE}/openDocumento.do?cDocId={cdoc_id}"


def _pdf_label(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("-", " ").replace("_", " ")
    return name[:500] or url


class SaldanaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Dream City + sede espublico + PLAU JCyL + IDECyL WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info.0")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier.0")
        raw_seeds = self.config.get("seed_urls") or DEFAULT_SEED_URLS
        self.seed_urls: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.seed_urls.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.seed_urls.append((str(item[0]), str(item[1])))
            else:
                self.seed_urls.append((str(item), str(item)))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._dossier_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._catalog_cache: list[dict[str, Any]] | None = None
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, sede: bool = False, dossier: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-saldana/1.0")},
        )
        if dossier:
            opener = self._dossier_opener
            retries = int(self.config.get("dossier_retries", 2))
            timeout = int(self.config.get("dossier_timeout_s", 90))
        elif sede:
            opener = self._opener
            retries = 1
            timeout = 60
        else:
            opener = urllib.request.build_opener()
            retries = 1
            timeout = 60
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                with opener.open(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, OSError, ConnectionError) as exc:
                last_err = exc
                if dossier and attempt + 1 < retries:
                    time.sleep(self.delay_s * (attempt + 2))
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError(f"fetch failed: {url}")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-saldana/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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
            text_m = re.search(rf'href="{re.escape(url)}"[^>]*>([^<]+)<', local, re.I)
            titulo = ""
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            spans = [_strip_html(s) for s in re.findall(r"<span>([^<]+)</span>", local)]
            categoria = procedimiento = descripcion = ""
            fecha = None
            for s in spans:
                if RE_FECHA_DMY.search(s):
                    fecha = _parse_fecha_dmy(s)
            if len(spans) >= 3:
                useful = [s for s in spans if s not in ("Categoría", "Descripción", "Fecha de Publicación")]
                if useful:
                    categoria = useful[0] if len(useful) > 2 else ""
                    procedimiento = useful[1] if len(useful) > 2 else useful[0]
                    descripcion = useful[-2] if len(useful) > 2 else useful[-1]
                    if not fecha:
                        fecha = _parse_fecha_dmy(useful[-1])
            rows.append(
                {
                    "titulo": (titulo or descripcion or url)[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion or titulo,
                    "fecha": fecha or _fecha_from_blob(titulo),
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
        if self._catalog_cache is not None:
            return list(self._catalog_cache)
        try:
            html = self._fetch(self.dossier_url, dossier=True)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if not url.startswith("http"):
                url = f"{self.sede_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        self._catalog_cache = rows
        return list(rows)

    def _collect_plau_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url, origen in (
            (
                f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={PLAU_PROVINCIA}&municipio={PLAU_MUNICIPIO}",
                "jcyl_plau",
            ),
            (
                f"{PLAU_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={PLAU_PROVINCIA}&municipio={PLAU_MUNICIPIO}",
                "jcyl_plai",
            ),
        ):
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for m in RE_PLAU_DOC.finditer(html):
                cdoc_id, plan_code = m.group(1), m.group(2)
                if plan_code in seen:
                    continue
                seen.add(plan_code)
                fecha = _fecha_from_blob(plan_code)
                titulo = plan_code
                local = html[max(0, m.start() - 600) : m.end() + 600]
                for cell in re.findall(r"<td[^>]*>(.*?)</td>", local, re.S):
                    text = _strip_html(cell)
                    if text and len(text) > 8 and "doGoBoletin" not in text and not text.isdigit():
                        titulo = text[:500]
                        break
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": fecha,
                        "url": _plau_doc_url(cdoc_id),
                        "pdf_url": f"http://www.jcyl.es/plaupdf//34/34157/{cdoc_id}/",
                        "origen": origen,
                        "plan_code": plan_code,
                    }
                )
        return rows

    def _collect_wp_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in ("/project/urbanismo/", "/project/documentacion-oficial/"):
            url = f"{self.web_base}{path}"
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = m.group(1)
                if not pdf_url.startswith("http"):
                    pdf_url = f"{self.web_base}{pdf_url}"
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                titulo = _pdf_label(pdf_url)
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(pdf_url),
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "origen": "wordpress_pdf",
                    }
                )
        return rows

    def _collect_wp_projects(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(f"{self.web_base}/wp-json/wp/v2/project?per_page=50")
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return rows
        if not isinstance(data, list):
            return rows
        for item in data:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or "")
            title = str((item.get("title") or {}).get("rendered") or slug)
            link = str(item.get("link") or f"{self.web_base}/project/{slug}/")
            if not RE_PROYECTO.search(title) and slug not in ("urbanismo", "documentacion-oficial"):
                continue
            fecha = str(item.get("modified") or item.get("date") or "")[:10] or None
            rows.append(
                {
                    "titulo": _strip_html(title)[:500],
                    "fecha": fecha,
                    "url": link,
                    "origen": "wordpress_project",
                }
            )
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, fallback_title in self.seed_urls:
            titulo = fallback_title
            try:
                html = self._fetch(url)
                title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
                if title_m:
                    titulo = _strip_html(title_m.group(1))
                    titulo = re.sub(r"\s*[-|]\s*Ayuntamiento de Saldaña.*$", "", titulo, flags=re.I).strip()
            except (urllib.error.URLError, OSError, ConnectionError):
                pass
            origen = "jcyl_planeamiento" if "jcyl.es" in url else "web_semilla"
            rows.append(
                {
                    "titulo": (titulo or fallback_title)[:500],
                    "url": url,
                    "origen": origen,
                }
            )
        return rows

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio.replace(chr(39), chr(39)+chr(39))}'",
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
                sector = str(props.get("n_sector") or "").strip()
                num = str(props.get("n_num_sect") or "").strip()
                titulo = sector or num
                if sector and num and sector != num:
                    titulo = f"{sector} ({num})"
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or props.get("n_instrum") or layer)
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
                    rec["sector_code"] = num
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
        cql = (
            f"n_mun='{self.wfs_municipio.replace(chr(39), chr(39)+chr(39))}' "
            f"AND (n_num_sect ILIKE '%{escaped}%' OR n_sector ILIKE '%{escaped}%')"
        )
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
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            geom = None
        if isinstance(geom, dict) and geom.get("type"):
            self._sector_geom_cache[norm] = {"geom_geojson": geom, "geometry_source_url": url}
            return geom, url
        self._sector_geom_cache[norm] = None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "expte", "sector_code"))
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
            if titulo and (titulo in wfs_title or wfs_title in titulo):
                for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
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

    def _plau_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("plan_code") or row["url"]),
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
        if row.get("plan_code"):
            rec["plan_code"] = row["plan_code"]
        self._attach_geometry(rec)
        return rec

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_PROYECTO.search(titulo):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
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

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n del planeamiento",
            row["titulo"],
        ):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
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
        for item in self._collect_tramites_catalog():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        doc_page = {
            "titulo": "Modelos licencia urbanística y documentación oficial",
            "url": f"{self.web_base}/project/documentacion-oficial/",
            "origen": "wordpress_tramite",
        }
        rec = self._tramite_to_licencia(doc_page)
        if rec and rec["id"] not in seen:
            seen.add(rec["id"])
            rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") in ("catalogo_tramites", "wordpress_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for item in self._collect_wfs_proyectos():
            add(item)
        for item in self._collect_plau_documents():
            add(self._plau_to_proyecto(item))
        for item in self._collect_wp_pdfs():
            add(self._generic_to_proyecto(item))
        for item in self._collect_wp_projects():
            add(self._generic_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_tramites_catalog():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau": sum(1 for r in rows if r.get("origen") in ("jcyl_plau", "jcyl_plai")),
            "wordpress": sum(1 for r in rows if r.get("origen") in ("wordpress_pdf", "wordpress_project")),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
