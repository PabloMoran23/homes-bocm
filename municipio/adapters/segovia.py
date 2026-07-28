from __future__ import annotations

import hashlib
import html as htmlmod
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

WEB_BASE = "https://www.segovia.es"
SEDE_BASE = "https://sede.segovia.es"
MUNICIPIO = "Segovia"
ID_PREFIX = "segovia"
WAYBACK_SNAPSHOT = "20250712100341"
WAYBACK_PREFIX = f"https://web.archive.org/web/{WAYBACK_SNAPSHOT}/"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ayuntamiento/planeamiento-urbanistico",
    f"{WEB_BASE}/ayuntamiento/planeamiento-urbanistico/pgou",
    f"{WEB_BASE}/ayuntamiento/planeamiento-urbanistico/modificaciones",
    f"{WEB_BASE}/area/urbanismo",
    f"{WEB_BASE}/area/urbanismo/pgou-consolidado",
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia urbanística de obras",
    "licencia ambiental",
    "declaración responsable de actos de uso del suelo",
    "comunicación de inicio de actividad sometida a licencia ambiental",
    "licencia para instalación en fachada",
    "licencia de acometida de agua y saneamiento",
    "licencia para tala de árboles",
)

PROYECTO_TRAMITE_PATTERNS: tuple[str, ...] = (
    "certificado urbanístico",
    "alineación oficial",
    "segregación",
    "parcelación",
    "actas de alineaciones",
    "información urbanística",
    "planeamiento",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia (?:de |municipal|ambiental|urban)|solicitud de licencia|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"obra mayor|vado|calicatas|demolici[oó]n|concesi[oó]n de licencia|"
    r"primera (?:ocupaci[oó]n|utilizaci)|pr[oó]rroga de licencias)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peahis|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto de actuaci|modificaci[oó]n|"
    r"reparcel|estudio de detalle|sector (?:uzd|su[- ]?nc|uld)|junta de compensaci|"
    r"evaluaci[oó]n ambiental|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"normalizaci[oó]n de fincas|suelo urbano|alineaciones y rasantes|"
    r"exposici[oó]n p[uú]blica|correcci[oó]n de error)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|convocatoria del pleno|acta de sesi[oó]n|junta de gobierno local|"
    r"subvenci[oó]n deportiv|empadron|tribut|matrimonio civil|"
    r"impuesto sobre actividades econ[oó]micas|cobranza relativo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_WEB_URBAN = re.compile(r'href="(/area/urbanismo/[^"#?]+)"', re.I)
RE_WEB_URBAN_WAYBACK = re.compile(
    r"(?:web\.archive\.org/web/\d+/)?(?:https?://)?(?:www\.)?segovia\.es(/area/urbanismo/[^\"#?\s]+)",
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)


def _wayback_url(url: str) -> str:
    return f"{WAYBACK_PREFIX}{url}"


def _unwrap_wayback_pdf(href: str) -> str | None:
    if href.lower().endswith(".pdf") or ".pdf" in href.lower():
        if href.startswith("http"):
            return href
        m = re.search(
            r"(?:web\.archive\.org/web/\d+/)?(?:https?://)?(?:www\.)?segovia\.es(/[^\"#?\s]+\.pdf[^\"#?\s]*)",
            href,
            re.I,
        )
        if m:
            return urljoin(f"{WEB_BASE}/", m.group(1))
    return None


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


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _clean_title(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio urban" in n or "convenio con" in n:
        return "convenio urbanístico"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or "plan especial" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "peahis" in n:
        return "PEAHIS"
    if "correcci" in n and "error" in n:
        return "corrección PGOU"
    if "exposici" in n and "públic" in n:
        return "exposición pública"
    if "licencia" in n and "concesi" in n:
        return "licencia urbanística"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class SegoviaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal web (noticias /area/urbanismo) + sede STA (tablón + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._prefer_wayback = bool(self.config.get("prefer_wayback", False))
        self._direct_blocked = self._prefer_wayback
        self._direct_timeout_s = float(self.config.get("direct_timeout_s", 8))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-segovia/1.0")}
        candidates: list[str] = []
        if not self._direct_blocked:
            candidates.append(url)
        if self.config.get("wayback_fallback", True):
            candidates.append(_wayback_url(url))
        last_err: urllib.error.URLError | None = None
        for attempt_url in candidates:
            ctx = None
            timeout = self._direct_timeout_s if attempt_url == url else 60.0
            if attempt_url == url and (use_sede_ssl or "sede.segovia.es" in url):
                ctx = self._ssl_ctx
            try:
                req = urllib.request.Request(attempt_url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt_url == url:
                    self._direct_blocked = True
        if last_err:
            raise last_err
        raise urllib.error.URLError("fetch failed")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-segovia/1.0")},
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
                titulo = _clean_title(str(props.get("n_titulo") or ""))
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
                    "titulo": titulo,
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
            if titulo and (titulo in wfs_title or wfs_title in titulo):
                for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
                    if wfs_rec.get(key) is not None:
                        rec[key] = wfs_rec[key]
                return

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    @staticmethod
    def _extract_tablon_dataset(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_PTS2_TABLON = "
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

    @staticmethod
    def _extract_catalog_items(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_CATSERV = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        items: list[dict[str, Any]] = []
        for row in data if isinstance(data, list) else []:
            dboid = str(row.get("dboid") or "")
            name = _clean_title(str(row.get("name") or ""))
            if not name or not dboid:
                continue
            items.append({"titulo": name, "dboid": dboid, "origen": "catalogo_tramites"})
        return items

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_tablon_dataset(html):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_catalog_items(html):
            rows.append(
                {
                    **item,
                    "url": self._tramite_url(item["dboid"]),
                }
            )
        return rows

    def _collect_web_pages(self) -> list[dict[str, Any]]:
        seen_paths: set[str] = set()
        records: list[dict[str, Any]] = []

        def add_path(path: str, *, origen: str, titulo: str | None = None, pdf_url: str | None = None) -> None:
            if not path:
                return
            if pdf_url:
                path_key = pdf_url
            elif path.startswith("http"):
                path_key = urllib.parse.urlparse(path).path
            else:
                path_key = path
            if path_key in seen_paths:
                return
            if "/area/urbanismo/" not in path_key and not pdf_url:
                return
            seen_paths.add(path_key)
            if path.startswith("http"):
                full = path
            else:
                full = urljoin(f"{self.web_base}/", path)
            slug_title = titulo or _clean_title(unquote(path_key.rsplit("/", 1)[-1]).replace("-", " "))
            rec: dict[str, Any] = {
                "titulo": slug_title,
                "url": full,
                "fecha": _fecha_from_text(slug_title),
                "origen": origen,
                "path": path_key,
            }
            if pdf_url:
                rec["pdf_url"] = pdf_url
            records.append(rec)

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            urban_paths: set[str] = set(RE_WEB_URBAN.findall(html))
            for m in RE_WEB_URBAN_WAYBACK.finditer(html):
                urban_paths.add(m.group(1))
            for href in sorted(urban_paths):
                add_path(href, origen="web_drupal")
            pdf_urls: set[str] = set()
            for href in RE_PDF.findall(html):
                pdf = urljoin(page_url, href)
                if "urban" in pdf.lower() or "pgou" in pdf.lower() or "peahis" in pdf.lower():
                    pdf_urls.add(pdf)
            for m in RE_PDF.finditer(html):
                if unwrapped := _unwrap_wayback_pdf(m.group(1)):
                    if any(k in unwrapped.lower() for k in ("urban", "pgou", "peahis")):
                        pdf_urls.add(unwrapped)
            for pdf in sorted(pdf_urls):
                name = unescape(unquote(Path(pdf).name))
                add_path(
                    page_url,
                    origen="web_pdf",
                    titulo=name,
                    pdf_url=pdf,
                )

        detail_fetches = 0
        max_detail = int(self.config.get("max_web_detail_fetches", 12))
        for rec in list(records):
            if rec.get("origen") != "web_drupal":
                continue
            if detail_fetches >= max_detail:
                break
            detail_fetches += 1
            try:
                html = self._fetch(rec["url"])
            except urllib.error.URLError:
                continue
            h1 = RE_H1.search(html)
            if h1:
                rec["titulo"] = _clean_title(h1.group(1))
            rec["fecha"] = rec.get("fecha") or _fecha_from_text(html[:8000])
            pdf_m = RE_PDF.search(html)
            if pdf_m:
                rec["pdf_url"] = urljoin(rec["url"], pdf_m.group(1))

        return records

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia", blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not any(p in titulo.lower() for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = titulo
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("dboid") or row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if m := RE_EXPTE.search(titulo):
            rec["expte"] = m.group(1)
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

        for item in self._tablon_rows():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._catalog_rows():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._tablon_rows():
            add(self._row_to_proyecto(item))

        for item in self._catalog_rows():
            titulo = item["titulo"]
            if any(p in titulo.lower() for p in PROYECTO_TRAMITE_PATTERNS) or RE_PROYECTO.search(titulo):
                add(self._row_to_proyecto(item))

        for item in self._collect_web_pages():
            add(self._row_to_proyecto(item))

        add(
            self._row_to_proyecto(
                {
                    "titulo": "PGOU documentos consolidados octubre 2024",
                    "url": f"{self.web_base}/area/urbanismo/pgou-consolidado",
                    "fecha": "2024-10-01",
                    "origen": "pgou_consolidado",
                }
            )
        )

        for wfs_rec in self._collect_wfs_proyectos():
            add(wfs_rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web_")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
