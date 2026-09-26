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

WP_BASE = "https://ayto-cabrerizos.com"
SEDE_BASE = "https://sedeelectronica.ayto-cabrerizos.com/eAdmin"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"
MUNICIPIO = "Cabrerizos"
ID_PREFIX = "cabrerizos"
PLAI_MUNICIPIO = 67
PLAI_PROVINCIA = 37

URBANISMO_URL = f"{WP_BASE}/urbanismo/"
FORMULARIOS_URL = f"{WP_BASE}/formularios-tramites/"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_TRAMITE_PAGES: list[tuple[str, str]] = [
    (
        f"{SEDE_BASE}/Registrar.do?action=infoTramite&tipoReg=16",
        "Consulta / certificación urbanística",
    ),
    (
        f"{SEDE_BASE}/Registrar.do?action=listadoEntradas",
        "Registro electrónico — trámites urbanismo",
    ),
    (URBANISMO_URL, "Urbanismo — planeamiento vigente y documentación"),
    (FORMULARIOS_URL, "Formularios e impresos de trámites"),
]

DEFAULT_IMPRESOS: list[tuple[str, str]] = [
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-LICENCIA-CONSTRUCCION_NUEVA_PLANTA.pdf", "Licencia construcción nueva planta"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-LICENCIA-AMPLIACION.pdf", "Licencia ampliación"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-LICENCIA-SEGREGACION.pdf", "Licencia segregación"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-LICENCIA_INSTALACION_GRUA.pdf", "Licencia instalación grúa"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-DECLARACION-RESPONSABLE-OBRAS_2.pdf", "Declaración responsable obras"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-DECLARACION-RESPONSABLE-FOTOVOLTAICAS.pdf", "Declaración responsable fotovoltaicas"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-DECLARACION-RESPONSABLE-OCUPACION-UTILIZACION.pdf", "Declaración responsable ocupación"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-CONSULTA_CERT_URBANISTICA.pdf", "Consulta / certificación urbanística"),
    (f"{WP_BASE}/wp-content/uploads/2024/05/URB-MODIFICIACION-REHABIL-REFORMA-TOTAL.pdf", "Licencia modificación / rehabilitación"),
]

RE_PDF_HREF = re.compile(
    r'href="((?:https://ayto-cabrerizos\.com)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|segregaci[oó]n|gr[uú]a|fotovolta|rehabilitaci[oó]n|"
    r"certificaci[oó]n urban|consulta urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de (?:actuaci|urban)|"
    r"estudio de detalle|modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|"
    r"sector|edicto|bando|actuaci[oó]n urban|peri\b|urbanizaci[oó]n|"
    r"unidad(?:es)? de ejecuci[oó]n|\bu\.?ur\b|\bur\.?con\b|\bi\.?ur\b|\ber-\d|"
    r"memoria|planos|bocyl|bop\b)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"U\.?\s*Ur\.?\s*[-.]?\s*\d+(?:\.\d+)?|"
    r"UR\.?\s*CON\.?\s*[-.]?\s*\d+|"
    r"I\.?\s*UR\.?\s*[-.]?\s*\d+|"
    r"UR[- ]?\d+|"
    r"PERI\s*ER[- ]?\d+|"
    r"SECTOR\s+[A-Z0-9.\- ]{2,30}|"
    r"LAS\s+DUNAS|"
    r"LA\s+CRUZ\s+DE\s+CHICOLA|"
    r"TESO\s+DE\s+LA\s+CRUZ|"
    r"JUAN\s+L[OÓ]PEZ|"
    r"MIGUEL\s+DELIBES"
    r")\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "", code)
    code = code.replace("UUR", "U.UR").replace("U.UR.", "U.UR-")
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


def _title_from_pdf_url(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = re.sub(r"[_\-]+", " ", name)
    return unescape(name).strip()[:500]


def _proyecto_tipo(blob: str, instrumento: str = "") -> str:
    n = f"{blob} {instrumento}".lower()
    if "normas urban" in n or "nnss" in n:
        return "normas urbanísticas"
    if "estudio de detalle" in n or "estudio-detalle" in n:
        return "estudio de detalle"
    if "peri" in n:
        return "PERI"
    if "urbanizaci" in n:
        return "proyecto urbanización"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or re.search(r"\bu\.?ur\b", n):
        return "plan parcial"
    if "sector" in n or "ur-" in n:
        return "sector urbanístico"
    if "licencia" in n:
        return "licencia"
    return "planeamiento"


class CabrerizosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi + eAdmin sede (tablón caído) + PLAI JCYL + IDECyL WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.plai_municipio = int(self.config.get("plai_municipio") or PLAI_MUNICIPIO)
        self.plai_provincia = int(self.config.get("plai_provincia") or PLAI_PROVINCIA)
        self.plau_url = str(
            self.config.get("plau_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={self.plai_provincia}&municipio={self.plai_municipio:03d}"
        )
        self.plai_url = str(
            self.config.get("plai_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={self.plai_provincia}&municipio={self.plai_municipio:03d}"
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
        raw_impresos = self.config.get("impresos") or DEFAULT_IMPRESOS
        self.impresos: list[tuple[str, str]] = []
        for item in raw_impresos:
            if isinstance(item, dict):
                self.impresos.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.impresos.append((str(item[0]), str(item[1])))
            else:
                self.impresos.append((str(item), str(item)))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cabrerizos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cabrerizos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _collect_wp_pdfs(self, seed_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(seed_url)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            url = m.group(1)
            if not url.startswith("http"):
                url = f"{self.wp_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            titulo = _title_from_pdf_url(url)
            if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(url):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": _fecha_from_url(url) or _fecha_from_blob(titulo),
                    "origen": "wp_pdf",
                    "pdf_url": url,
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
            if len(cells) < 4 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            doc_m = (
                re.search(r"doGoBoletin\('(\d+)'", tr)
                or re.search(r"doOpen\('(\d+)'", tr)
                or re.search(r"openDocuIndice\.do[^\"']*cDocId=(\d+)", tr)
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
                    "fecha": cells[2] if len(cells) > 2 else "",
                    "instrumento": f"{cells[0]} {cells[1]}".strip(),
                    "doc_id": doc_id,
                    "origen": "plau_jcyl",
                }
            )
        return rows

    def _collect_plau(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (self.plau_url, self.plai_url):
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for item in self._parse_plau_rows(html, page_url):
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
                        "origen": item.get("origen"),
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
                    titulo = str(props.get("n_titulo") or props.get("c_id_sect") or props.get("c_plan") or layer)
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
                    for code in _sector_codes_from_text(f"{num} {sector}"):
                        self._sector_geom_cache[_normalize_sector_code(code)] = {
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
            f"AND (n_num_sect ILIKE '%{escaped}%' OR c_id_sect ILIKE '%{escaped}%' OR n_sector ILIKE '%{escaped}%')"
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "sector_code", "instrumento"))
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

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("url") or row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("instrumento", "")),
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

    def _collect_tramite_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in self.tramite_pages:
            rows.append({"titulo": titulo[:500], "url": url, "origen": "tramite_info"})
        return rows

    def _collect_impresos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in self.impresos:
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": _fecha_from_url(url),
                    "origen": "wp_impreso",
                    "pdf_url": url,
                }
            )
        return rows

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; sede eAdmin tablón HTTP 500",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_tramite_pages() + self._collect_impresos():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wfs_proyectos():
            by_id[rec["id"]] = rec
        for item in self._collect_plau():
            rec = self._row_to_proyecto(item)
            by_id[rec["id"]] = rec
        for item in self._collect_wp_pdfs(URBANISMO_URL):
            rec = self._row_to_proyecto(item)
            by_id[rec["id"]] = rec
        for item in self._collect_tramite_pages():
            if RE_PROYECTO.search(item["titulo"]):
                rec = self._row_to_proyecto(item)
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_info"),
            "impresos": sum(1 for r in rows if r.get("origen") == "wp_impreso"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias():
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
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau_jcyl": sum(1 for r in rows if r.get("origen") == "plau_jcyl"),
            "wp_pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
