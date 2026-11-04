from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

TRAMITEGUNEA_BASE = "https://tramitegunea.erandio.eus"
APP_BASE = "https://app.erandio.eus"
MUNICIPIO = "Erandio"
ID_PREFIX = "erandio"

BIZKAIA_PUR_URL = (
    "https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador"
    "?p_p_id=IYBIWPUC_INSTANCE_CadYBlTy6tfn&p_p_lifecycle=0"
    "&p_p_state=normal&p_p_mode=view"
)
BIZKAIA_MUNICIPIO_ID = "902"

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/Plangintza_Planeamiento/MapServer"
)
GEOM_LAYER_IDS = (41, 42, 23)
CLASIFICACION_LAYERS: tuple[tuple[int, str], ...] = (
    (1, "Urbano"),
    (2, "Urbanizable"),
    (3, "No urbanizable"),
)

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    (f"{TRAMITEGUNEA_BASE}/?lang=es", "Manual de trámites municipales (Tramitegunea)"),
    (f"{APP_BASE}/territo/", "Área de Territorio — urbanismo y obras"),
    (
        f"{TRAMITEGUNEA_BASE}/front/procedure/174?lang=es",
        "Información urbanística (trámite municipal)",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra(s)?\s+(?:menor|mayor)|parcelaci|"
    r"demolici|derrumbe|movimiento de tierras|primera utilizaci|gr[uú]a|"
    r"ocupaci[oó]n de v[ií]a p[uú]blica|terraza|velador|ascensor|"
    r"actividad clasificada|reforma integral)",
)
RE_LICENCIA_EXCLUDE = re.compile(
    r"(?i)(autotaxi|animal|cementer|exhum|plusval|veh[ií]culo|incidencia|"
    r"potencialmente peligros|feria|circo|publicitaria|autotaxi)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|instrumento|sector|peri|unidad de ejecuci)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BIZKAIA_CARD = re.compile(
    r'role="heading"[^>]*>(\d{4})</p>\s*<p>([^<]+)</p>.*?'
    r'href="([^"]+_IYBIWPUC_INSTANCE_CadYBlTy6tfn_idInstrumento=\d+[^"]*)"',
    re.S | re.I,
)
RE_BIZKAIA_CODE = re.compile(
    r'<span class="mw-100 text-right">\(([^)]+)\)</span>',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="(https://tramitegunea\.erandio\.eus/front/procedure/\d+\?lang=es)"[^>]*>([^<]+)',
    re.I,
)
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{4,}")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2035
    ]
    if not years:
        return None
    return f"{max(years)}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob or "peri" in blob:
        return "plan especial"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "modificaci" in blob:
        return "modificación puntual"
    if "unidad de ejecuci" in blob:
        return "unidad de ejecución"
    if "informaci" in blob and "pública" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio"
    return "planeamiento"


def _tokens_from_title(title: str, *, max_tokens: int = 6) -> list[str]:
    stop = {
        "plan", "parcial", "especial", "ordenacion", "ordenación", "urbana", "urbano",
        "suelo", "sector", "modif", "tercera", "segunda", "primera", "area", "área",
        "actuacion", "actuación", "del", "de", "la", "el", "en", "los", "las", "para",
        "con", "una", "uno", "mixto", "residencial", "urbanizable",
    }
    raw = [t.upper() for t in RE_TOKEN.findall(title or "")]
    out: list[str] = []
    for t in raw:
        if t.lower() in stop or len(t) < 4:
            continue
        if t not in out:
            out.append(t)
        if len(out) >= max_tokens:
            break
    return out


class ErandioAyuntamientoAdapter(AyuntamientoAdapter):
    """
    Tramitegunea (trámites/licencias informativas) + Registro PUR Diputación Bizkaia (902).
    Geometría parcial vía ArcGIS Plangintza (NombreAmbito + clasificación suelo).
    """

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRAMITEGUNEA_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.fetch_timeout_s = float(self.config.get("fetch_timeout_s", 25))
        self.bizkaia_municipio_id = str(
            self.config.get("bizkaia_municipio_id") or BIZKAIA_MUNICIPIO_ID
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 40))
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.geom_layer_ids = tuple(
            int(x) for x in (self.config.get("geometry_layer_ids") or GEOM_LAYER_IDS)
        )
        raw_seeds = self.config.get("licencia_seeds")
        if raw_seeds:
            self.licencia_seeds = [(str(s["url"]), str(s["titulo"])) for s in raw_seeds]
        else:
            self.licencia_seeds = list(DEFAULT_LICENCIA_SEEDS)
        self._geometry_attempts = 0

    def _fetch(
        self, url: str, data: bytes | None = None, *, timeout_s: float | None = None
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-erandio/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s or self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _bizkaia_form_date(self) -> str:
        try:
            html = self._fetch(BIZKAIA_PUR_URL)
        except (urllib.error.URLError, TimeoutError, OSError):
            return str(int(time.time() * 1000))
        m = re.search(
            r'name="_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate"[^>]*value="(\d+)"',
            html,
            re.I,
        )
        return m.group(1) if m else str(int(time.time() * 1000))

    def _collect_bizkaia_planeamiento(self) -> list[dict[str, Any]]:
        form_date = self._bizkaia_form_date()
        payload = urllib.parse.urlencode(
            {
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate": form_date,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-municipios": self.bizkaia_municipio_id,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-figuras": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_filtro-texto": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_submit": "Buscar",
            }
        ).encode("utf-8")
        try:
            html = self._fetch(BIZKAIA_PUR_URL, data=payload)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BIZKAIA_CARD.finditer(html):
            year, titulo, url = m.group(1), unescape(m.group(2).strip()), m.group(3)
            titulo = re.sub(r"\s+", " ", titulo)
            block = m.group(0)
            code_m = RE_BIZKAIA_CODE.search(block)
            codigo = code_m.group(1).strip() if code_m else None
            inst_m = re.search(r"idInstrumento=(\d+)", url)
            inst_id = inst_m.group(1) if inst_m else url
            detail_url = url if url.startswith("http") else f"https://www.bizkaia.eus{url}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"bizkaia-pur-{inst_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": f"{year}",
                "tipo": _tipo_proyecto(titulo),
                "url": detail_url,
                "source": "ayuntamiento",
                "origen": "bizkaia_pur",
                "instrumento_id": inst_id,
            }
            if codigo:
                rec["codigo_instrumento"] = codigo
            rows.append(rec)
        return rows

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        if self._geometry_attempts > self.geometry_max_rows * len(self.geom_layer_ids):
            return None
        tokens = _tokens_from_title(title)
        if not tokens:
            return None
        for token in tokens:
            where = f"Municipio='ERANDIO' AND UPPER(NombreAmbito) LIKE '%{token}%'"
            for layer_id in self.geom_layer_ids:
                self._geometry_attempts += 1
                params = {
                    "where": where,
                    "outFields": "NombreAmbito,Municipio",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultRecordCount": "1",
                }
                url = f"{self.arcgis_map}/{layer_id}/query?{urllib.parse.urlencode(params)}"
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                    continue
                feats = data.get("features") if isinstance(data, dict) else None
                if not feats:
                    continue
                geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
                if not isinstance(geom, dict) or not geom.get("type"):
                    continue
                return {
                    "geom_geojson": geom,
                    "geometry_crs": "EPSG:4326",
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if not self.geometry_enrich or record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        cen = geometry_centroid(geom["geom_geojson"])
        if cen:
            rec["lat"], rec["lon"] = cen

    def _arcgis_clasificacion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for layer_id, label in CLASIFICACION_LAYERS:
            params = {
                "where": "Municipio='ERANDIO'",
                "outFields": "Municipio,ClasificacionCA,OBJECTID",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "1",
            }
            url = f"{self.arcgis_map}/{layer_id}/query?{urllib.parse.urlencode(params)}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                continue
            feats = data.get("features") if isinstance(data, dict) else None
            if not feats:
                continue
            geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
            if not isinstance(geom, dict):
                continue
            titulo = f"PGOU Erandio — suelo {label} (Diputación Foral de Bizkaia)"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"arcgis-clas-{layer_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": "2023",
                "tipo": "PGOU",
                "url": BIZKAIA_PUR_URL,
                "source": "ayuntamiento",
                "origen": "diputacion_arcgis_clasificacion",
                "geom_geojson": geom,
                "geometry_source": "portal_visor_arcgis",
                "geometry_source_url": url,
                "coord_source": "portal_geometry_centroid",
                "geometry_crs": "EPSG:4326",
            }
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_tramitegunea_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, nota: str) -> None:
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                return
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": nota,
                    "origen": "tramitegunea",
                }
            )

        for url, titulo in self.licencia_seeds:
            add(url, titulo, "Página informativa; sin listado público de concesiones")

        try:
            html = self._fetch(f"{TRAMITEGUNEA_BASE}/?lang=es")
        except (urllib.error.URLError, TimeoutError, OSError):
            return rows

        for m in RE_TRAMITE_LINK.finditer(html):
            url, text = m.group(1), _strip_html(m.group(2))
            if RE_LICENCIA_EXCLUDE.search(text):
                continue
            if not RE_LICENCIA.search(text):
                continue
            add(url, text, "Ficha del manual de trámites (Tramitegunea)")
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        rows = self._collect_tramitegunea_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramitegunea": len(rows),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._arcgis_clasificacion_rows():
            add(rec)

        pur_rows = self._collect_bizkaia_planeamiento()
        enriched = 0
        for rec in pur_rows:
            self._attach_geometry(rec)
            if record_geometry(rec):
                enriched += 1
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "bizkaia_pur": len(pur_rows),
            "pur_with_geometry": enriched,
            "with_geometry": with_geom,
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
