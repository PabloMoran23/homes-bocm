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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.zamora.es"
SEDE_BASE = "https://zamora.sedelectronica.es"
MUNICIPIO = "Zamora"
ID_PREFIX = "zamora"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_URLS: list[tuple[str, str]] = [
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=275",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=49&municipio=275",
        "Planeamiento urbanístico en información pública (Junta CYL)",
    ),
    (f"{WEB_BASE}/contenidos.aspx?id=309", "Planeamiento Vigente"),
    (f"{WEB_BASE}/contenidos.aspx?id=32474", "Planeamiento de Desarrollo"),
    (f"{WEB_BASE}/contenidos.aspx?id=32637", "Planes de Actuación"),
    (f"{WEB_BASE}/contenidos.aspx?id=555", "Planos P.G.O.U."),
    (f"{WEB_BASE}/contenidos.aspx?id=32470", "Planos P.E.C.H.-A."),
]

DEFAULT_WEB_SEED_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/contenidos.aspx?id=309", "Planeamiento Vigente"),
    (f"{WEB_BASE}/contenidos.aspx?id=32474", "Planeamiento de Desarrollo"),
    (f"{WEB_BASE}/contenidos.aspx?id=32637", "Planes de Actuación"),
    (f"{WEB_BASE}/contenidos.aspx?id=31409", "Transparencia Urbanismo, Obras y Medioambiente"),
    (f"{WEB_BASE}/contenidos.aspx?id=31904", "Actas Comisión de Urbanismo, Medioambiente y Obras"),
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/contenidos.aspx?id=152", "Licencia Urbanística — procedimiento abreviado (obra menor)"),
    (f"{WEB_BASE}/contenidos.aspx?id=153", "Licencia Urbanística — procedimiento ordinario (obra mayor)"),
    (f"{WEB_BASE}/contenidos.aspx?id=148", "Licencia Ambiental"),
    (f"{WEB_BASE}/contenidos.aspx?id=155", "Declaración Responsable de Obras (DRO)"),
    (f"{WEB_BASE}/contenidos.aspx?id=149", "Modificación de Licencia Ambiental y Comunicación Ambiental"),
    (f"{WEB_BASE}/contenidos.aspx?id=21044", "Licencia de Segregación"),
    (f"{SEDE_BASE}/board", "Tablón de anuncios — sede electrónica"),
]

RE_PREVIEW = re.compile(
    r'href="(https://zamora\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|primera utilizaci[oó]n|ambiental|dro\b|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pech|pepcha|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|urbanizaci[oó]n|"
    r"normas urban|instrumento|memoria|planos|bocyl|eulalia|humanizaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|proceso selectivo|pleno|"
    r"plusvalia|basura|residuos|veh[ií]culos|notificaci[oó]n expediente|igualdad|"
    r"jurado|juez de paz|pe[oó]n|iae|cobranza|teletrabajo|calendario fiscal|"
    r"selecci[oó]n de personal|tribunal|convocatoria pleno|monitor actividades|"
    r"electores|icio\b|ordenanza fiscal|sancionador.*tr[aá]fico|bolsa de empleo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_CONTENIDOS = re.compile(r'href="(contenidos\.aspx\?id=\d+)"', re.I)
RE_TITLE = re.compile(r"<title>\s*([^<]+)\s*</title>", re.I)


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
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _fecha_from_year(text: str) -> str | None:
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "pech" in n or "pepcha" in n or "conjunto hist" in n:
        return "plan especial protección"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or " pp " in n:
        return "plan parcial"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    if "humanizaci" in n:
        return "humanización urbana"
    if "sector" in n:
        return "sector"
    if "licencia" in n:
        return "licencia"
    return "urbanismo"


class ZamoraAyuntamientoAdapter(AyuntamientoAdapter):
    """Web ASP.NET zamora.es + sede espublico (board/transparency) + IDECyL WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        raw_seeds = self.config.get("seed_urls") or DEFAULT_SEED_URLS
        self.seed_urls: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.seed_urls.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.seed_urls.append((str(item[0]), str(item[1])))
            else:
                self.seed_urls.append((str(item), str(item)))
        raw_web = self.config.get("web_seed_pages") or DEFAULT_WEB_SEED_PAGES
        self.web_seed_pages: list[tuple[str, str]] = []
        for item in raw_web:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                self.web_seed_pages.append((str(item[0]), str(item[1])))
            else:
                self.web_seed_pages.append((str(item), str(item)))
        raw_lic = self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES
        self.licencia_pages: list[tuple[str, str]] = []
        for item in raw_lic:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                self.licencia_pages.append((str(item[0]), str(item[1])))
            else:
                self.licencia_pages.append((str(item), str(item)))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-zamora/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-zamora/1.0")},
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
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else titulo,
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
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
        for url, origen in (
            (self.board_url, "tablon"),
            (self.transparency_url, "transparencia"),
        ):
            try:
                html = self._fetch(url, sede=True)
            except (urllib.error.URLError, OSError, ConnectionError, TimeoutError):
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, fallback_title in self.seed_urls:
            titulo = fallback_title
            try:
                html = self._fetch(url)
                title_m = RE_TITLE.search(html)
                if title_m:
                    titulo = _strip_html(title_m.group(1))
            except (urllib.error.URLError, OSError, ConnectionError, TimeoutError):
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

    def _collect_web_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, section_title in self.web_seed_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError, ConnectionError, TimeoutError):
                continue
            for m in RE_PDF.finditer(html):
                href = m.group(1)
                pdf_url = urljoin(page_url, href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = unescape(unquote(Path(pdf_url).name.replace("%20", " ")))
                blob = f"{name} {section_title}"
                if not RE_PROYECTO.search(blob) and not any(
                    k in blob.lower() for k in ("pgou", "pech", "urban", "sector", "plan", "estudio")
                ):
                    continue
                rows.append(
                    {
                        "titulo": name[:500] or section_title,
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "fecha": _fecha_from_blob(name) or _fecha_from_year(name),
                        "origen": "web_pdf",
                        "section": section_title,
                    }
                )
            for m in RE_CONTENIDOS.finditer(html):
                href = m.group(1)
                child_url = urljoin(page_url, href)
                if child_url in seen:
                    continue
                local = html[max(0, m.start() - 120) : m.end() + 120]
                text_m = re.search(rf'href="{re.escape(href)}"[^>]*>([^<]+)<', local, re.I)
                if not text_m:
                    continue
                titulo = _strip_html(text_m.group(1))
                if not RE_PROYECTO.search(titulo):
                    continue
                seen.add(child_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": child_url,
                        "fecha": _fecha_from_blob(titulo),
                        "origen": "web_contenidos",
                        "section": section_title,
                    }
                )
        return rows

    def _wfs_query_url(self, layer: str) -> str:
        escaped = self.wfs_municipio.replace("'", "''")
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": f"n_mun = '{escaped}'",
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
                sector = str(props.get("n_sector") or "").strip()
                num = str(props.get("n_num_sect") or "").strip()
                if not titulo:
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

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        sector_id = str(rec.get("sector_id") or "").lower()
        tokens = [t for t in re.split(r"[\s,/()-]+", titulo) if len(t) >= 4]
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            wfs_sector = str(wfs_rec.get("sector_id") or "").lower()
            if sector_id and sector_id == wfs_sector:
                self._copy_geometry(wfs_rec, rec)
                return
            if titulo and (titulo in wfs_title or wfs_title in titulo):
                self._copy_geometry(wfs_rec, rec)
                return
            for token in tokens:
                if token in wfs_title or token in wfs_sector:
                    self._copy_geometry(wfs_rec, rec)
                    return

    @staticmethod
    def _copy_geometry(src: dict[str, Any], dst: dict[str, Any]) -> None:
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if src.get(key) is not None:
                dst[key] = src[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob) and not RE_LICENCIA.search(blob):
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
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() in ("urbanismo", "ordenanzas y reglamentos"):
            if not RE_PROYECTO.search(blob) and "ordenanza" not in blob.lower():
                return None
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

    def _tramite_to_licencia(self, url: str, tipo: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": tipo,
            "url": url,
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "web_tramite",
        }

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('section', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha") or _fecha_from_blob(titulo) or _fecha_from_year(titulo),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
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
        for url, tipo in self.licencia_pages:
            rec = self._tramite_to_licencia(url, tipo)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_wfs_proyectos():
            add(item)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._generic_to_proyecto(item))
        for item in self._collect_web_documents():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "source": "ayuntamiento",
            "adapter": self.__class__.__name__,
            "at": datetime.now(timezone.utc).isoformat(),
        }

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
