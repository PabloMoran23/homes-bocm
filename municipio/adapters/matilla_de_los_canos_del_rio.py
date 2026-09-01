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

SEDE_BASE = "https://matilladeloscanos.sedelectronica.es"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"
MUNICIPIO = "Matilla de los Caños del Río"
ID_PREFIX = "matilla-canos-rio"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_TRAMITE_PAGES: list[tuple[str, str]] = [
    (
        f"{SEDE_BASE}/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a",
        "Declaración Responsable o Comunicación en Materia Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/15fabacb-83b1-47d1-b435-508245672051",
        "Solicitud de Licencia o Autorización Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae",
        "Solicitud de Modificación o Renuncia de Licencia Urbanística",
    ),
    (
        f"{SEDE_BASE}/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f",
        "Solicitud de Licencia de Ocupación",
    ),
    (
        f"{SEDE_BASE}/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf",
        "Solicitud de Certificado o Informe Urbanístico",
    ),
    (
        f"{SEDE_BASE}/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26",
        "Modificación del Planeamiento de Desarrollo",
    ),
    (
        f"{SEDE_BASE}/catalog/t/96514574-aca1-40e1-a800-e06485e6d016",
        "Planeamiento General (Modificación)",
    ),
    (
        f"{SEDE_BASE}/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f",
        "Solicitud de Actuación Urbanística",
    ),
]

RE_PREVIEW = re.compile(
    r'href="(https://matilladeloscanos\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://matilladeloscanos\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|primera utilizaci[oó]n|ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|ruina|desafectaci[oó]n|"
    r"unidad(?:es)? de ejecuci[oó]n|suelo urbano|su[- ]?nc|s\.u\.n\.c|"
    r"normas urban|junta de compensaci[oó]n|regularizaci[oó]n|urbanizaci[oó]n)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"PE[- ]?\d+|AR[- ]?P\d+|UNC\d+|"
    r"S\.?\s*U\.?\s*\.?\s*N\.?\s*C\.?\s*[-.]?\s*(?:UNC)?\d*|"
    r"SU[- ]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+(?:[-/]\d+)?|"
    r"sector\s*\d+"
    r")\b",
)
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
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "", code)
    code = code.replace("AR-P", "AR-P").replace("PE-", "PE-")
    if re.fullmatch(r"UNC\d+", code):
        return code
    if re.fullmatch(r"PE\d+", code):
        return f"PE-{code[2:]}"
    if re.fullmatch(r"ARP\d+", code):
        return f"AR-P{code[3:]}"
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


def _proyecto_tipo(blob: str, instrumento: str = "") -> str:
    n = f"{blob} {instrumento}".lower()
    if "normas urban" in n or n.strip() == "num":
        return "normas urbanísticas"
    if "plan especial" in n or re.search(r"\bpe[- ]?\d+\b", n):
        return "plan especial"
    if "junta de compensaci" in n:
        return "junta de compensación"
    if "urbanizaci" in n:
        return "proyecto urbanización"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "licencia" in n:
        return "licencia"
    if "planeam" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


class MatillaDeLosCanosDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + PlanPublica PLAU + IDECyL WFS (web corporativa inestable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info.0")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier/.0")
        self.plau_url = str(
            self.config.get("plau_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=187"
        )
        self.plai_url = str(
            self.config.get("plai_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=187"
        )
        raw_tramites = self.config.get("tramite_pages") or DEFAULT_TRAMITE_PAGES
        self.tramite_pages: list[tuple[str, str]] = []
        for item in raw_tramites:
            if isinstance(item, dict):
                self.tramite_pages.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.tramite_pages.append((str(item[0]), str(item[1])))
            else:
                self.tramite_pages.append((str(item), str(item)))
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
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-matilla-canos-rio/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-matilla-canos-rio/1.0")},
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

    def _collect_tramites_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.dossier_url, sede=True)
        except (urllib.error.URLError, OSError, ConnectionError):
            html = ""
        if html:
            for m in RE_CATALOG.finditer(html):
                url, titulo = m.group(1), unescape(m.group(2).strip())
                if not url.startswith("http"):
                    url = f"{self.sede_base}{url}"
                if url in seen:
                    continue
                seen.add(url)
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        for url, titulo in self.tramite_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
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
            if len(cells) < 4 or cells[0] in {"Libro", "Tipo"}:
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
            url = (
                f"{PLAU_BASE}/openDocumento.do?cDocId={doc_id}"
                if doc_id
                else fallback_url
            )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": cells[2],
                    "instrumento": f"{cells[0]} {cells[1]}".strip(),
                    "subtipo": cells[1] if len(cells) > 1 else "",
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
                    "subtipo": item.get("subtipo") or "",
                    "doc_id": item.get("doc_id") or None,
                    "origen": "plau_jcyl",
                }
            )
        return rows

    def _collect_plai_seed(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.plai_url)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._parse_plau_rows(html, self.plai_url):
            rows.append(
                {
                    "titulo": item["title"][:500],
                    "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                    "url": item["url"],
                    "instrumento": item.get("instrumento") or "",
                    "origen": "plai_jcyl",
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
            f"AND (n_num_sect ILIKE '%{escaped}%' OR c_id_sect ILIKE '%{escaped}%')"
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
        blob = " ".join(
            str(rec.get(k) or "")
            for k in ("titulo", "descripcion", "expte", "sector_code", "instrumento")
        )
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
        subtipo = str(rec.get("subtipo") or "").upper()
        if subtipo == "NUM":
            for wfs_rec in self._collect_wfs_proyectos():
                if wfs_rec.get("wfs_layer") == "urbanismo:plau_cyl_instrumentos_ambito":
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
        key = row.get("doc_id") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"plau:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("instrumento", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "instrumento": row.get("instrumento") or None,
            "subtipo": row.get("subtipo") or None,
        }
        if row.get("doc_id"):
            rec["doc_id"] = row["doc_id"]
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
            "fecha": row.get("fecha"),
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
        for item in self._collect_wfs_proyectos():
            if item["id"] not in seen:
                seen.add(item["id"])
                rows.append(item)
        for item in self._collect_plau():
            rec = self._plau_to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_plai_seed():
            rec = self._tramite_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites_catalog():
            rec = self._tramite_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau": sum(1 for r in rows if r.get("origen") == "plau_jcyl"),
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
