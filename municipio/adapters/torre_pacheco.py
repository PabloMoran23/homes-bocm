from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.torrepacheco.es"
SEDE_BASE = "https://sede.torrepacheco.es"
TRANSPARENCIA_BASE = "https://transparencia.torrepacheco.es"
MUNICIPIO = "Torre-Pacheco"
ID_PREFIX = "torre-pacheco"
COD_INE = "30037"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Torre%20Pacheco%27"
    "&count=500&outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_SEEDS = (
    f"{TRANSPARENCIA_BASE}/5991-2/",
    f"{WEB_BASE}/servicios-municipales/urbanismo/",
)

LICENCIA_TRAMITE_NAMES: tuple[str, ...] = (
    "licencia urbanística",
    "declaración responsable de obras",
    "comunicacion previa de obras",
    "comunicación previa de obras",
    "instancia y/o comunicación urbanística",
    "licencia de actividad",
    "declaración responsable de 1ª ocupación",
    "declaración responsable de 2ª ocupación",
    "convenio urbanístico",
    "proyecto de urbanización",
    "certificado urbanístico",
    "informe urbanístico",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|informaci[oó]n p[uú]blica.*licencia|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|edicto|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"sector|aur\b|rold[aá]n|ordenanza urban|evaluaci[oó]n ambiental|"
    r"delimitaci[oó]n|urbanizaci[oó]n|avance de planeamiento)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|pad[ró]n municipal|pleno ordinario|subvenci[oó]n|"
    r"plan estrat[eé]gico de subvenciones|plan de ordenaci[oó]n de recursos humanos|"
    r"plan anual normativo|tasa|agua|basura|aparcamiento subterr[aá]neo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AUR = re.compile(r"(?i)\bAUR\s*n[ºo°.]?\s*(\d+)")
RE_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]{4,200})', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _norm_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "plan parcial" in b or "aur" in b:
        return "plan parcial"
    if "plan especial" in b or "rold" in b:
        return "plan especial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


def _ambito_tokens(blob: str) -> list[str]:
    tokens: list[str] = []
    norm = _norm_key(blob)
    for m in RE_AUR.finditer(blob or ""):
        tokens.append(f"aur {m.group(1)}")
    if "roldan" in norm:
        tokens.append("roldan")
    for word in norm.split():
        if len(word) >= 5 and word not in {"torre", "pacheco", "ayuntamiento", "municipal"}:
            tokens.append(word)
    return tokens


class TorrePachecoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón + catálogo) + transparencia WP + WFS SITMURCIA (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEEDS)]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torre-pacheco/1.0")},
        )
        ctx = self._ssl_ctx if sede_ssl or self.sede_base in url else None
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                    raw = resp.read()
                for enc in ("utf-8", "latin-1", "iso-8859-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.35 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

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

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _strip_html(
                str(item.get("descriptionProc") or item.get("externString") or "")
            )
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or "")
            blob = f"{titulo} {remitente}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")) or _fecha_from_blob(blob),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "origen": "tablon_sta",
                    "blob": blob,
                }
            )
        return rows

    def _collect_catalogo_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        names_lower = tuple(n.lower() for n in LICENCIA_TRAMITE_NAMES)
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _strip_html(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            nl = name.lower()
            if not any(pat in nl for pat in names_lower):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": None,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_sta",
                    "blob": name,
                    "es_licencia": True,
                }
            )
        return rows

    def _collect_transparencia_links(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for href, title in RE_LINK.findall(html):
                titulo = _strip_html(title)
                blob = f"{titulo} {href}"
                if not RE_PROYECTO.search(blob) and "urbanismo" not in href.lower():
                    continue
                if RE_TABLON_SKIP.search(blob):
                    continue
                url = href if href.startswith("http") else urllib.parse.urljoin(seed, href)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": titulo[:500] or "Documento transparencia",
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "origen": "transparencia_web",
                        "blob": blob,
                    }
                )
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            ambito_raw = str(props.get("Ambito") or "").strip()
            geom = feat.get("geometry")
            if not ambito_raw or not isinstance(geom, dict):
                continue
            key = _norm_key(ambito_raw)
            rec = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito_raw,
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[key] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "blob", "descripcion"))
        tokens = _ambito_tokens(blob)
        if not tokens:
            return
        index = self._build_wfs_index()
        best_key: str | None = None
        best_score = 0
        for key, hit in index.items():
            score = sum(1 for t in tokens if t in key)
            if score > best_score:
                best_score = score
                best_key = key
        if best_key and best_score >= 1:
            hit = index[best_key]
            for field in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "ambito",
                "clasificacion",
                "geometry_crs",
                "geometry_axis_order",
            ):
                if hit.get(field) is not None:
                    rec[field] = hit[field]

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.sede_base)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if raw.get("es_licencia"):
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob) and not raw.get("es_licencia"):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.sede_base)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob) or "1970-01-01",
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
        }
        self._attach_geometry(rec)
        if rec.get("lat") is None or rec.get("lon") is None:
            centroid = self.config.get("centroid") or [37.7439, -0.9538]
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = rec.get("coord_source") or "municipio_centroid"
        rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for src in (
            self._collect_tablon(),
            self._collect_transparencia_links(),
        ):
            for raw in src:
                rec = self._to_proyecto(raw)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_tablon() + self._collect_catalogo_tramites():
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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
        return {**stats, "added": max(0, after - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyecto_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_web"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
        return {**stats, "added": max(0, after - before)}
