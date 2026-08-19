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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.mirandadeebro.es"
WP_API = f"{WEB_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://sede.mirandadeebro.es"
MUNICIPIO = "Miranda de Ebro"
ID_PREFIX = "miranda-de-ebro"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
URBANISMO_KEYWORD = "PTS_PC_012"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ayuntamiento/servicios/area-de-urbanismo/",
    f"{WEB_BASE}/ayuntamiento/servicios/area-de-urbanismo/a-r-u/",
    f"{WEB_BASE}/ayuntamiento/servicios/area-de-urbanismo/e-r-r-p/",
    f"{WEB_BASE}/ayuntamiento/servicios/area-de-urbanismo/e-r-r-p-2/",
    f"{WEB_BASE}/ayuntamiento/servicios/area-de-urbanismo/a-r-u/obras-de-urbanizacion/",
    f"{WEB_BASE}/tipo-documentacion/planes-urbanisticos/",
    f"{WEB_BASE}/transparencia/urbanismo-obras-publicas-y-medio-ambiente/ordenacion-urbana/",
    f"{WEB_BASE}/documentacion/archivo-de-planeamiento-urbanistico/",
]

DEFAULT_JCYL_SEEDS: list[tuple[str, str]] = [
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=219",
        "Planeamiento en información pública (Junta CYL)",
    ),
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=219",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/documentacion/solicitud-de-licencia-de-obra-mayor/", "Solicitud licencia obra mayor"),
    (f"{WEB_BASE}/documentacion/solicitud-de-licencia-de-obra-menor/", "Solicitud licencia obra menor"),
    (
        f"{WEB_BASE}/documentacion/solicitud-de-licencia-de-obra-proyecto-de-ejecucion/",
        "Solicitud licencia obra (proyecto ejecución)",
    ),
    (f"{WEB_BASE}/documentacion/solicitud-de-licencia-de-primera-ocupacion/", "Solicitud licencia primera ocupación"),
    (f"{WEB_BASE}/documentacion/comunicacion-ambiental/", "Comunicación ambiental"),
    (
        f"{WEB_BASE}/documentacion/solicitud-de-informacion-urbanistica-cedula-urbanistica/",
        "Solicitud cédula urbanística",
    ),
    (f"{WEB_BASE}/documentacion/solicitud-de-planos-de-urbanismo/", "Solicitud planos urbanismo"),
    (f"{WEB_BASE}/documentacion/solicitud-de-parcelacion-urbanistica/", "Solicitud parcelación urbanística"),
    (
        f"{WEB_BASE}/documentacion/solicitud-de-licencia-para-ocupacion-de-la-via-publica-con-vallas-andamios-contenedores-etc/",
        "Licencia ocupación vía pública",
    ),
    (f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON", "Tablón anuncios sede electrónica"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|cedula urban|c[eé]dula urban|comunicaci[oó]n ambiental|"
    r"parcelaci[oó]n urban|planos de urbanismo|ocupaci[oó]n de la v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|aru|e\.?r\.?r\.?p|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|actuaci[oó]n urban|urbanizaci[oó]n|instrumento|ued|plan parcial|"
    r"ordenaci[oó]n urbana|archivo de planeamiento)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(bolsa de empleo|convocatoria y bases|proceso selectivo|subvenci[oó]n deportiv|"
    r"empadron|tribut|matrimonio|residuos s[oó]lidos urbanos|autob[uú]s urbano|"
    r"dormideros urbanos|mercados zonas urbanas|plotter|software|antivirus|oracle|"
    r"kaspersky|fotograf[ií]a|colonias felinas|estornino)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?mirandadeebro\.es)?(?:/wp-content/uploads/[^"\']+\.pdf|/PDFS/[^"\']+\.pdf)[^"\']*)["\']',
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
    years = re.findall(r"\b((?:19|20)\d{2})\b", text or "")
    valid = [int(y) for y in years if 1980 <= int(y) <= 2035]
    if valid:
        return f"{max(valid)}-01-01"
    return None


def _iso_date_wp(value: str) -> str | None:
    return _parse_fecha_iso(value)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "aru" in n:
        return "ARU"
    if "e.r.r.p" in n or "errp" in n:
        return "ERRP"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n:
        return "plan parcial"
    if "estudio de detalle" in n or "ued" in n:
        return "estudio de detalle"
    if "urbaniz" in n:
        return "urbanización"
    if "licencia" in n and "concesi" in n:
        return "licencia urbanística"
    if "pgou" in n or "planeam" in n or "ordenaci" in n:
        return "planeamiento"
    return "urbanismo"


class MirandaDeEbroAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress mirandadeebro.es + IDECyL WFS + sede STA (tablón si accesible)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        raw_jcyl = self.config.get("jcyl_seeds") or DEFAULT_JCYL_SEEDS
        self.jcyl_seeds: list[tuple[str, str]] = []
        for item in raw_jcyl:
            if isinstance(item, dict):
                self.jcyl_seeds.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.jcyl_seeds.append((str(item[0]), str(item[1])))
        self.licencia_pages = list(self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _abs_wp(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urljoin(f"{self.web_base}/", href.lstrip("/"))

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-miranda-de-ebro/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.mirandadeebro.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-miranda-de-ebro/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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
            if len(token) < 4:
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

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&DETALLE={code}&PAGE_CODE=CATALOGO"
            )
            rows.append({"name": name, "code": code, "url": url})
        return rows

    def _xml_date(obj: dict[str, Any] | None) -> str | None:
        if not obj or not isinstance(obj, dict):
            return None
        try:
            return datetime(
                int(obj["year"]),
                int(obj["month"]),
                int(obj["day"]),
            ).strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError):
            return None

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        fecha = self._xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, fecha, expte, url

    def _paginate_wp(self, endpoint: str, max_pages: int = 8) -> list[dict[str, Any]]:
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

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
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
                if not RE_PROYECTO.search(blob) and "urban" not in page_url.lower():
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

    def _wp_doc_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
        if not title or RE_EXCLUDE.search(title):
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
            "origen": "wp_documentacion",
        }
        pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
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
            "url": row.get("url") or row.get("pdf_url") or f"{self.web_base}/ayuntamiento/servicios/area-de-urbanismo/",
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _jcyl_seed_proyecto(self, url: str, titulo: str) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": None,
            "tipo": "planeamiento",
            "url": url,
            "source": "ayuntamiento",
            "origen": "jcyl_plan_publica",
        }
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, fecha, expte, url = self._tablon_row(row)
        if not RE_LICENCIA.search(title):
            return None
        key = expte or url
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tramite_to_licencia(self, url: str, tipo: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": tipo[:500],
            "url": url,
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "wp_tramite",
        }

    def _catalog_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Catálogo sede electrónica",
            "origen": "catalogo",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, fecha, expte, url = self._tablon_row(row)
        blob = title
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = expte or url
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or _fecha_from_blob(title),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "expte": expte or None,
            "origen": "tablon",
        }
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
        for url, tipo in self.licencia_pages:
            rec = self._tramite_to_licencia(url, tipo)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._paginate_wp("documentacion"):
            title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
            url = str(item.get("link") or "")
            if not url or not RE_LICENCIA.search(title):
                continue
            rec = self._tramite_to_licencia(url, title[:200])
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_tramites():
            rec = self._catalog_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for url, titulo in self.jcyl_seeds:
            add(self._jcyl_seed_proyecto(url, titulo))
        for item in self._paginate_wp("documentacion", max_pages=10):
            add(self._wp_doc_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for row in self._collect_tablon():
            add(self._tablon_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "wp_documentacion": sum(1 for r in rows if r.get("origen") == "wp_documentacion"),
            "wp_pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "jcyl": sum(1 for r in rows if r.get("origen") == "jcyl_plan_publica"),
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
