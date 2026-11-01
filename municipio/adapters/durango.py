from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

PORTAL_BASE = "https://www.durango.eus"
SEDE_BASE = "https://egoitza-sede.durango.eus"
PARTEHARTU_BASE = "https://partehartu.durango.eus"
MUNICIPIO = "Durango"
ID_PREFIX = "durango"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
URBANISTICAS_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_URBANISTICAS"
)
BOLOFICIAL_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_BOLOFICIAL"
RSS_BANDOS = f"{PORTAL_BASE}/es/rss/bandos-y-anuncios"
RSS_NOTICIAS = f"{PORTAL_BASE}/es/rss/noticias"
PARTEHARTU_ABIERTOS = f"{PARTEHARTU_BASE}/proyecto-de-participaci%C3%B3n"

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/PX_Durango_inf/MapServer"
)
GEOM_LAYER_IDS = (50, 91, 97, 132)

DEFAULT_DOCUMENTED_PROYECTOS: list[dict[str, Any]] = [
    {
        "titulo": (
            "Aprobada inicialmente la tercera fase del proyecto de urbanización (Zona D) "
            "de la unidad de ejecución UE-7 Azoka-Montevideo"
        ),
        "url": f"{PORTAL_BASE}/es/home",
        "fecha": '2026',
        "tipo": "urbanización",
        "geom_tokens": ["Azoka", "Montevideo", "UE-7"],
    },
    {
        "titulo": (
            "Consulta previa sobre la modificación puntual de las NNSS en el ámbito PERI-1 Ferrocarril"
        ),
        "url": PARTEHARTU_ABIERTOS,
        "fecha": "2026-10-19",
        "tipo": "modificación puntual",
        "geom_tokens": ["PERI-1", "PERI"],
    },
]

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    (f"{SEDE_BASE}/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=PTS2_HOME", "Sede electrónica — trámites"),
    (
        f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON",
        "Tablón de anuncios (sede)",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:menor|mayor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|unidad de ejecuci[oó]n|\bue-\d|nnss|"
    r"aprobaci[oó]n (?:inicial|definitiva)|ferrocarril|azoka)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = (blob or "").lower()
    if "peri" in b:
        return "plan especial (PERI)"
    if "unidad de ejecuci" in b or re.search(r"\bue-\d", b):
        return "unidad de ejecución"
    if "urbaniz" in b:
        return "urbanización"
    if "modificaci" in b and ("nnss" in b or "norm" in b):
        return "modificación puntual"
    if "informaci" in b and "públic" in b:
        return "información pública"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b:
        return "plan parcial"
    if "convenio" in b:
        return "convenio urbanístico"
    return "planeamiento urbanístico"


class DurangoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón/urbanísticas) + RSS bandos + Parte Hartu; geometría Diputación Bizkaia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.fetch_timeout_s = float(self.config.get("fetch_timeout_s", 25))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl"):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        raw_doc = self.config.get("documented_proyectos")
        self.documented_proyectos = list(raw_doc) if raw_doc else list(DEFAULT_DOCUMENTED_PROYECTOS)
        raw_tram = self.config.get("licencia_tramites")
        if raw_tram:
            self.licencia_tramites = [(str(t[0]), str(t[1])) for t in raw_tram if len(t) >= 2]
        else:
            self.licencia_tramites = list(DEFAULT_LICENCIA_TRAMITES)
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.geom_layer_ids = tuple(
            int(x) for x in (self.config.get("geometry_layer_ids") or GEOM_LAYER_IDS)
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 8))
        self.geometry_max_tokens = int(self.config.get("geometry_max_tokens", 3))
        self.geometry_max_layers = int(self.config.get("geometry_max_layers", 4))
        self.centroid_lat = float(self.config.get("centroid_lat", 43.1689))
        self.centroid_lng = float(self.config.get("centroid_lng", -2.6335))
        self._geometry_attempts = 0

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-durango/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            needle = f"var dataset_{dataset_name} = ["
            start = html.find(needle)
            if start < 0:
                return []
            chunk = html[start + len(needle) - 1 : html.find("];", start) + 1]
        else:
            end = html.find("];", start)
            if end < 0:
                return []
            chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _tablon_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, dataset in ((TABLON_URL, "PTS2_TABLON"), (URBANISTICAS_URL, "PTS2_URBANISTICAS")):
            try:
                html = self._fetch(url, use_sede_ssl=True)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for item in self._extract_sta_dataset(html, dataset):
                if isinstance(item, dict):
                    item = {**item, "_source_url": url, "_dataset": dataset}
                    rows.append(item)
        return rows

    def _sta_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        base = str(row.get("_source_url") or TABLON_URL)
        url = f"{base}#dboid={dboid}"
        return title, remitente, fecha, url

    def _parse_rss(self, url: str) -> list[dict[str, str]]:
        try:
            raw = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        out: list[dict[str, str]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
            fecha = _fecha_from_text(pub) or ""
            if title:
                out.append({"titulo": title, "url": link or url, "fecha": fecha})
        return out

    def _parse_partehartu(self) -> list[dict[str, str]]:
        try:
            html = self._fetch(PARTEHARTU_ABIERTOS)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, str]] = []
        for m in re.finditer(
            r"<h[23][^>]*>([^<]+)</h[23]>.*?Fecha inicio\s*</[^>]+>\s*(\d{2}-\d{2}-\d{4})",
            html,
            re.S | re.I,
        ):
            titulo = _strip_html(m.group(1))
            fecha = _parse_fecha_dmy(m.group(2).replace("-", "/")) or ""
            if titulo:
                rows.append({"titulo": titulo, "url": PARTEHARTU_ABIERTOS, "fecha": fecha})
        if not rows:
            for m in re.finditer(r"<h[23][^>]*>([^<]{15,})</h[23]>", html, re.I):
                titulo = _strip_html(m.group(1))
                if RE_PROYECTO.search(titulo):
                    rows.append({"titulo": titulo, "url": PARTEHARTU_ABIERTOS, "fecha": ""})
        return rows

    def _geom_tokens(self, text: str, extra: list[str] | None = None) -> list[str]:
        stop = {
            "durango",
            "ayuntamiento",
            "modificacion",
            "consulta",
            "previa",
            "proyecto",
            "aprobada",
            "inicialmente",
            "tercera",
            "fase",
            "sobre",
            "ambito",
            "puntual",
        }
        seen: set[str] = set()
        out: list[str] = []
        for tok in extra or []:
            key = tok.lower()
            if key not in seen and len(key) >= 4:
                seen.add(key)
                out.append(tok)
        for m in RE_TOKEN.finditer(text or ""):
            w = m.group(0)
            key = w.lower()
            if key in stop or len(key) < 4:
                continue
            if key not in seen:
                seen.add(key)
                out.append(w)
        return out[: self.geometry_max_tokens]

    def _geometry_plausible(self, geom: dict[str, Any]) -> bool:
        centroid = geometry_centroid(geom)
        if not centroid:
            return False
        lat, lon = centroid
        return (
            abs(lat - self.centroid_lat) <= 0.12
            and abs(lon - self.centroid_lng) <= 0.12
        )

    def _fetch_geometry(self, titulo: str, extra_tokens: list[str] | None = None) -> dict[str, Any] | None:
        if not self.geometry_enrich or self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        layer_ids = self.geom_layer_ids[: self.geometry_max_layers]
        for token in self._geom_tokens(titulo, extra_tokens):
            esc = token.replace("'", "''")
            where = f"(DESCRIPCION LIKE '%{esc}%' OR ETIQUETA LIKE '%{esc}%')"
            for layer_id in layer_ids:
                params = {
                    "where": where,
                    "outFields": "ETIQUETA,DESCRIPCION",
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
                if not self._geometry_plausible(geom):
                    continue
                return {
                    "geom_geojson": geom,
                    "geometry_crs": "EPSG:4326",
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _attach_geometry(self, rec: dict[str, Any], extra_tokens: list[str] | None = None) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""), extra_tokens)
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

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

    def _title_to_licencia(self, title: str, url: str, fecha: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str,
        *,
        geom_tokens: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{title}"),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
        }
        self._attach_geometry(rec, geom_tokens)
        return rec

    def _informative_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in self.licencia_tramites:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                }
            )
        return rows

    def _collect_proyectos(self, tablon: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        tablon_rows = tablon if tablon is not None else self._tablon_rows()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in tablon_rows:
            title, rem, fecha, url = self._sta_row_to_record(item)
            add(self._title_to_proyecto(f"{title} {rem}".strip(), url, fecha))

        for item in self._parse_rss(RSS_BANDOS) + self._parse_rss(RSS_NOTICIAS):
            add(self._title_to_proyecto(item["titulo"], item["url"], item.get("fecha") or ""))

        for item in self._parse_partehartu():
            add(self._title_to_proyecto(item["titulo"], item["url"], item.get("fecha") or ""))

        for doc in self.documented_proyectos:
            titulo = str(doc.get("titulo") or "")
            url = str(doc.get("url") or PORTAL_BASE)
            fecha = str(doc.get("fecha") or "") or (_fecha_from_text(titulo) or "")
            tokens = [str(t) for t in (doc.get("geom_tokens") or [])]
            add(self._title_to_proyecto(titulo, url, fecha, geom_tokens=tokens))

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._tablon_rows():
            title, _, fecha, url = self._sta_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._informative_licencias():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_licencias": len(rows) - len(self.licencia_tramites)}

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
        tablon = self._tablon_rows()
        rows = self._collect_proyectos(tablon)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "sources": {
                "tablon": len(tablon),
                "documented": len(self.documented_proyectos),
            },
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
