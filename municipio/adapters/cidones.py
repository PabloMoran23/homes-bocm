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

WEB_BASE = "https://www.cidones.es"
SEDE_BASE = "https://ayuntamientocidones.sedelectronica.es"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
MUNICIPIO = "Cidones"
ID_PREFIX = "cidones"

WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
WFS_C_MUN = "42061"
WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/informacion-urbanistica",
    f"{WEB_BASE}/modelos-de-solicitudes",
    f"{WEB_BASE}/ordenanzas-y-reglamentos",
]

DEFAULT_TRAMITE_PAGES: list[tuple[str, str]] = [
    (
        f"{WEB_BASE}/sites/cidones.es/files/public/pags/solicitud_licencia_obra.docx",
        "Solicitud de licencia de obra",
    ),
    (
        f"{WEB_BASE}/sites/cidones.es/files/public/pags/3._declaracion_responsable_sede22112024114947.pdf",
        "Declaración responsable (licencia urbanística)",
    ),
    (
        f"{WEB_BASE}/sites/cidones.es/files/public/pags/declaracion_responsable_1a_ocupacion.pdf",
        "Declaración responsable primera ocupación",
    ),
    (
        f"{WEB_BASE}/sites/cidones.es/files/public/pags/solicitud_informe_urbanistico.docx",
        "Solicitud de informe urbanístico",
    ),
    (
        f"{WEB_BASE}/sites/cidones.es/files/public/pags/ordenanza_tasa_licencias_y_declar._responsables.pdf",
        "Ordenanza de tasas de licencias y declaraciones responsables",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|num|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|sector|"
    r"edicto|actuaci[oó]n urban|reclasificaci[oó]n|suelo r[uú]stico|instrumento|bocyl|"
    r"correcci[oó]n de error)",
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector\s*(?:n[ºo°]\.?\s*)?(\d{1,3})|s[- ]?(\d{1,3}))\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?cidones\.es)?/sites/cidones\.es/files/[^"\']+\.(?:pdf|docx)[^"\']*)["\']',
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


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_dmy(text)


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = (m.group(1) or m.group(2) or "").strip()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str, instrumento: str = "") -> str:
    n = f"{blob} {instrumento}".lower()
    if "normas urban" in n or re.search(r"\bnum\b", n):
        return "normas urbanísticas"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual NUM"
    if "correcci" in n and "error" in n:
        return "corrección de errores"
    if "reclasificaci" in n:
        return "reclasificación de suelo"
    if "sector" in n:
        return "sector"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "planeam" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


class CidonesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 + PLAU JCyL + IDECyL WFS (geometría partial). Sede espublico no accesible."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.plau_url = str(
            self.config.get("plau_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=061"
        )
        self.plai_url = str(
            self.config.get("plai_url")
            or f"{PLAU_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=061"
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        raw_tramites = self.config.get("tramite_pages") or DEFAULT_TRAMITE_PAGES
        self.tramite_pages: list[tuple[str, str]] = []
        for item in raw_tramites:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                self.tramite_pages.append((str(item[0]), str(item[1])))
            elif isinstance(item, dict):
                self.tramite_pages.append((str(item["url"]), str(item.get("titulo") or item["url"])))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_c_mun = str(self.config.get("wfs_c_mun") or WFS_C_MUN)
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._sector_geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cidones/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    @staticmethod
    def _parse_plau_rows(html: str, fallback_url: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c and c != "\xa0"]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
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

    def _collect_plai(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.plai_url)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._parse_plau_rows(html, self.plai_url):
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
                    "origen": "plai_jcyl",
                }
            )
        return rows

    def _collect_drupal_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                url = self._abs_web(href)
                if url in seen:
                    continue
                seen.add(url)
                filename = unescape(urllib.parse.unquote(url.rsplit("/", 1)[-1]))
                titulo = filename.replace("_", " ").rsplit(".", 1)[0]
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(filename),
                        "origen": "drupal_pdf",
                        "page_url": page_url,
                    }
                )
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
                "count": "120",
                "CQL_FILTER": f"c_mun = '{self.wfs_c_mun}'",
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
                    if num:
                        self._sector_geom_cache[num] = {
                            "geom_geojson": geom,
                            "geometry_source_url": url,
                        }
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _wfs_sector_geometry(self, sector_code: str) -> tuple[dict[str, Any] | None, str | None]:
        if sector_code in self._sector_geom_cache:
            hit = self._sector_geom_cache[sector_code]
            if hit:
                return hit["geom_geojson"], hit["geometry_source_url"]
            return None, None
        escaped = sector_code.replace("'", "''")
        cql = (
            f"c_mun='{self.wfs_c_mun}' "
            f"AND (n_num_sect ILIKE '%{escaped}%' OR c_id_sect ILIKE '%{escaped}%')"
        )
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "urbanismo:plau_cyl_sectores",
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
            self._sector_geom_cache[sector_code] = {"geom_geojson": geom, "geometry_source_url": url}
            return geom, url
        self._sector_geom_cache[sector_code] = None
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
        if subtipo == "NUM" or "normas urban" in blob.lower():
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

    def _drupal_pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
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

    def _tramite_to_licencia(self, url: str, titulo: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": url,
            "source": "ayuntamiento",
            "nota": "Modelo/formulario informativo; no concesión publicada en tablón",
            "origen": "drupal_modelo",
        }

    def _drupal_pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
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
            "nota": "Documento informativo; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

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
        for url, titulo in self.tramite_pages:
            rec = self._tramite_to_licencia(url, titulo)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_drupal_pdfs():
            rec = self._drupal_pdf_to_licencia(item)
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
        for item in self._collect_plau():
            add(self._plau_to_proyecto(item))
        for item in self._collect_plai():
            add(self._plau_to_proyecto(item))
        for item in self._collect_drupal_pdfs():
            add(self._drupal_pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau": sum(1 for r in rows if r.get("origen") in {"plau_jcyl", "plai_jcyl"}),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
