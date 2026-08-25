from __future__ import annotations

import hashlib
import http.client
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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.ponferrada.org"
URBANISMO_BASE = f"{WEB_BASE}/es/ponferrada-temas/obras-urbanismo"
MUNICIPIO = "Ponferrada"
ID_PREFIX = "ponferrada"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
PLAN_BASE = "https://servicios.jcyl.es/PlanPublica"
PLAN_PROVINCIA = 24
PLAN_MUNICIPIO = 115
SIUR_URL = "https://idecyl.jcyl.es/siur/index.html?id=24115"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_PLAN_SEEDS: list[tuple[str, str]] = [
    (
        f"{PLAN_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={PLAN_PROVINCIA}&municipio={PLAN_MUNICIPIO}",
        "Planeamiento en información pública (Junta CYL)",
    ),
    (
        f"{PLAN_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={PLAN_PROVINCIA}&municipio={PLAN_MUNICIPIO}",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
]

DEFAULT_TRAMITE_PAGES: list[str] = [
    f"{URBANISMO_BASE}/tramites/licencia-urbanistica",
    f"{URBANISMO_BASE}/tramites/declaracion-responsable-obras-menores",
    f"{URBANISMO_BASE}/tramites/declaracion-responsable-actos-constructivos-constructivos",
    f"{URBANISMO_BASE}/tramites/declaracion-responsable-actos-uso-suelo",
    f"{URBANISMO_BASE}/tramites/licencia-segregacion-division-parcelaciones-urbanisticas",
    f"{URBANISMO_BASE}/tramites/consultas-certificados-urbanisticos",
    f"{URBANISMO_BASE}/tramites/solicitud-implantacion-veladores-nueva-implantacion",
    f"{URBANISMO_BASE}/servicios/planeamiento-urbanistico-jcyl",
    f"{URBANISMO_BASE}/servicios/archivo-planeamiento-urbanistico-plau",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|cedula urban|c[eé]dula urban|comunicaci[oó]n ambiental|"
    r"parcelaci[oó]n urban|certificado urban|velador|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|aru|pau|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|actuaci[oó]n urban|urbanizaci[oó]n|instrumento|ssunc|s\.?u\.?n\.?c|"
    r"ordenaci[oó]n|convenio urban|normalizaci[oó]n|concurso de ideas)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"S\.?\s*S\.?\s*U\.?\s*\.?\s*N\.?\s*C\.?\s*[-.]?\s*(?:\d+|[A-Z]\d+)?|"
    r"SSUNC[-\s]?\d+(?:[-/]\d+)?|"
    r"SUNC[-\s]?\d+(?:[-/]\d+)?|"
    r"SU[- ]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+(?:[-/]\d+)?|"
    r"SUD[-\s]?\d+(?:[-/]\d+)?"
    r")\b",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]n.*vivienda|alquiler vivienda|calderas|accesibilidad vivienda|"
    r"rehabilitaci[oó]n edificatoria|bolsa de empleo|convocatoria y bases|"
    r"empadron|tribut|ruido estrat[eé]gico|mapa estrat[eé]gico)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(
    r'href=["\']([^"\']+\.(?:pdf|zip)(?:\?[^"\']*)?)["\']',
    re.I,
)
RE_PAGE_LINK = re.compile(
    r'href="(/es/ponferrada-temas/obras-urbanismo/(?:servicios|noticias-novedades|normativa)[^"?#]*)"'
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = re.findall(r"\b((?:19|20)\d{2})\b", text or "")
    valid = [int(y) for y in years if 1980 <= int(y) <= 2035]
    if valid:
        return f"{max(valid)}-01-01"
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = re.sub(r"S\. S\. U\. N\. C\.", "SSUNC", code)
    code = re.sub(r"S\.U\.N\.C\.", "SSUNC", code)
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
    if "aru" in n:
        return "ARU"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or " p.p." in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "urbaniz" in n:
        return "urbanización"
    if "modificaci" in n:
        return "modificación puntual"
    if "pgou" in n or "planeam" in n or "ordenaci" in n:
        return "planeamiento"
    return "urbanismo"


class PonferradaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Proxia Ecclesia (obras-urbanismo) + PlanPublica JCyL + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.tramite_pages = list(self.config.get("tramite_pages") or DEFAULT_TRAMITE_PAGES)
        raw_seeds = self.config.get("plan_seeds") or DEFAULT_PLAN_SEEDS
        self.plan_seeds: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.plan_seeds.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.plan_seeds.append((str(item[0]), str(item[1])))
            else:
                self.plan_seeds.append((str(item), str(item)))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self.plan_provincia = int(self.config.get("plan_provincia") or PLAN_PROVINCIA)
        self.plan_municipio = int(self.config.get("plan_municipio") or PLAN_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _abs_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urljoin(f"{self.web_base}/", href.lstrip("/"))

    def _fetch(self, url: str, *, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ponferrada/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (http.client.IncompleteRead, urllib.error.URLError, OSError, ConnectionError) as exc:
                last_err = exc
                if attempt + 1 < retries:
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ponferrada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _title_from_url(url: str) -> str:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        slug = re.sub(r"\.nodos,\d+,\d+$", "", slug)
        return slug.replace("-", " ").strip().title()

    def _page_title(self, html: str, fallback: str = "", *, url: str = "") -> str:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if h1:
            title = _strip_html(h1.group(1))
            if title and not re.fullmatch(r"(?i)ayuntamiento de ponferrada", title):
                return title
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if title_m:
            title = _strip_html(title_m.group(1))
            title = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", title, flags=re.I).strip()
            if title and not re.fullmatch(r"(?i)ayuntamiento de ponferrada", title):
                return title
        if url:
            from_url = self._title_from_url(url)
            if from_url:
                return from_url
        return fallback or (self._title_from_url(url) if url else "")

    def _crawl_section(self, section: str, *, max_pages: int = 12) -> list[str]:
        prefix = f"/es/ponferrada-temas/obras-urbanismo/{section}"
        start = f"{self.web_base}{prefix}"
        seen: set[str] = set()
        queue: list[str] = [start]
        urls: list[str] = []
        while queue and len(seen) < max_pages:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for m in RE_PAGE_LINK.finditer(html):
                path = m.group(1)
                if path.endswith((".nodos",)) or ".nodos," in path:
                    continue
                if path.startswith(prefix) and path.count("/") >= prefix.count("/") + 1:
                    full = f"{self.web_base}{path}"
                    if full not in seen:
                        urls.append(full)
            for m in re.finditer(
                rf'href="({re.escape(prefix)}\.nodos,\d+,\d+)"',
                html,
            ):
                queue.append(f"{self.web_base}{m.group(1)}")
            for m in re.finditer(
                rf'href="({re.escape(prefix)}/[^"?#]+)"',
                html,
            ):
                full = f"{self.web_base}{m.group(1)}"
                if full not in seen and ".ficheros/" not in full:
                    urls.append(full)
        return sorted(set(urls))

    def _collect_web_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for section, origen in (
            ("servicios", "web_servicios"),
            ("noticias-novedades", "web_noticias"),
            ("normativa", "web_normativa"),
        ):
            for url in self._crawl_section(section):
                if url in seen:
                    continue
                seen.add(url)
                try:
                    html = self._fetch(url)
                except (urllib.error.URLError, OSError, ConnectionError):
                    continue
                titulo = self._page_title(
                    html,
                    self._title_from_url(url),
                    url=url,
                )
                blob = f"{titulo} {url}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if section != "servicios":
                        continue
                fecha = _fecha_from_blob(titulo + " " + html[:2000])
                pdf_url = None
                for m in RE_PDF_HREF.finditer(html):
                    href = self._abs_url(m.group(1))
                    if "ponferrada.org" in href:
                        pdf_url = href
                        break
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": fecha,
                        "pdf_url": pdf_url,
                        "origen": origen,
                    }
                )
        return rows

    def _collect_tramite_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.tramite_pages:
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError, http.client.IncompleteRead):
                titulo = self._title_from_url(url)
            else:
                titulo = self._page_title(html, self._title_from_url(url), url=url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "web_tramite",
                }
            )
        return rows

    def _parse_plan_rows(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [_strip_html(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            cells = [c for c in cells if c]
            if len(cells) < 4 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            fecha_pub = cells[2] if len(cells) > 2 else ""
            doc_m = re.search(r"doOpen\('?(\d+)'?", tr)
            boletin_m = re.search(r"doGoBoletin\('?(\d+)'?", tr)
            if doc_m:
                url = f"{PLAN_BASE}/openDocumento.do?cDocId={doc_m.group(1)}"
            elif boletin_m:
                url = f"{PLAN_BASE}/openBoletinDoc.do?cDocId={boletin_m.group(1)}"
            else:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_pub),
                    "url": url,
                    "instrumento": cells[1] if len(cells) > 1 else "",
                    "origen": origen,
                }
            )
        return rows

    def _collect_planpublica(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        endpoints = [
            (
                f"{PLAN_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={self.plan_provincia}&municipio={self.plan_municipio}",
                "plai_jcyl",
            ),
            (
                f"{PLAN_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={self.plan_provincia}&municipio={self.plan_municipio}",
                "plau_jcyl",
            ),
        ]
        for url, origen in endpoints:
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for item in self._parse_plan_rows(html, origen):
                key = item["url"] + item["titulo"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "500",
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
                if sector and num:
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
                doc_url = str(props.get("url_doc_info") or "").strip() or SIUR_URL
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
            f"AND n_num_sect ILIKE '%{escaped}%'"
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "sector_code"))
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
                ):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
                return

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('url', '')}"
        if row.get("origen") != "web_tramite" and not RE_LICENCIA.search(blob):
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

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('instrumento', '')} {row.get('url', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("instrumento"):
            rec["instrumento"] = row["instrumento"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        for item in self._collect_tramite_pages():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "source": "ayuntamiento",
            "adapter": self.__class__.__name__,
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        prev = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        result = self.backfill_licencias(out_jsonl)
        merged = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        for pid, row in prev.items():
            merged.setdefault(pid, row)
        self._write_jsonl(out_jsonl, list(merged.values()))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )
        return {**result, "rows": len(merged)}

    def _safe_collect(self, label: str, fn) -> list[dict[str, Any]]:
        try:
            return fn()
        except (urllib.error.URLError, OSError, ConnectionError, http.client.IncompleteRead, json.JSONDecodeError) as exc:
            return [{"_error": label, "_message": str(exc)}]

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for item in self._collect_wfs_proyectos():
            if item["id"] not in seen:
                seen.add(item["id"])
                rows.append(item)
        for batch in (
            self._safe_collect("planpublica", self._collect_planpublica),
            self._safe_collect("web_pages", self._collect_web_pages),
        ):
            if len(batch) == 1 and batch[0].get("_error"):
                errors.append(f"{batch[0]['_error']}: {batch[0]['_message']}")
                continue
            for item in batch:
                rec = self._row_to_proyecto(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        for seed_url, seed_title in self.plan_seeds:
            rec = self._row_to_proyecto(
                {
                    "titulo": seed_title,
                    "url": seed_url,
                    "origen": "jcyl_planeamiento",
                }
            )
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        result: dict[str, Any] = {
            "rows": len(rows),
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "source": "ayuntamiento",
            "adapter": self.__class__.__name__,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if errors:
            result["warnings"] = errors
        return result

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        prev = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        result = self.backfill_proyectos(out_jsonl)
        merged = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        for pid, row in prev.items():
            merged.setdefault(pid, row)
        self._write_jsonl(out_jsonl, list(merged.values()))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )
        return {**result, "rows": len(merged)}
