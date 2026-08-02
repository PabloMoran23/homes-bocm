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
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WEB_BASE = "https://cercedilla.es"
SEDE_BASE = "https://sederecaudacioncercedilla.eadministracion.es"
URBANISMO_URL = f"{WEB_BASE}/departamento-de-urbanismo/"
PGOU_URL = f"{WEB_BASE}/avance-plan-general-ordenacion-urbana-cercedilla/"
ANUNCIOS_URL = f"{WEB_BASE}/anuncios-oficiales/"
MUNICIPIO = "Cercedilla"
ID_PREFIX = "cercedilla"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "CERCEDILLA"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    PGOU_URL,
]

AMBITO_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("matalavieja", "UA-SU-2 MATALAVIEJA"),
    ("fuenfria", "UA-SU-6 LA FUENFRIA"),
    ("fuenfría", "UA-SU-6 LA FUENFRIA"),
    ("quinyones", "UA-SU-4 LOS QUIÑONES"),
    ("quiñones", "UA-SU-4 LOS QUIÑONES"),
    ("arroyuelos", "SAU-3 LOS ARROYUELOS"),
    ("navalcaballo", "SAU-2 NAVALCABALLO"),
    ("las fuentes", "SAU-1 LAS FUENTES"),
    ("ua-su-1", "UA-SU-1"),
    ("ua-su-2", "UA-SU-2 MATALAVIEJA"),
    ("ua-su-3", "UA-SU-3"),
    ("ua-su-4", "UA-SU-4 LOS QUIÑONES"),
    ("ua-su-5", "UA-SU-5"),
    ("ua-su-6", "UA-SU-6 LA FUENFRIA"),
    ("sau-1", "SAU-1 LAS FUENTES"),
    ("sau-2", "SAU-2 NAVALCABALLO"),
    ("sau-3", "SAU-3 LOS ARROYUELOS"),
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"ordenanza.*licencia|primera ocupaci|calificaci[oó]n urban|parcelaci[oó]n|alineaci[oó]n|"
    r"tala de [aá]rbol|certificado urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgouc|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|normas subsidiarias|"
    r"ordenanza|edtu|sector|urbanizaci[oó]n|calificaci[oó]n urban|avance)",
)
RE_ANUNCIOS_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pgou|ordenanza.*(?:suelo|edific|urban)|bocm.*(?:urban|plan|licen|orden)|"
    r"informaci[oó]n p[uú]blica|convenio|parcela|estudio de detalle|edificaci|memoria|peri|"
    r"nnss|normas subsidiarias|calificaci[oó]n|avance.*plan)",
)
RE_PGOU_PLANO_SHEET = re.compile(
    r"(?i)(?:^|/)(?:PI|PO|DIE)-\d{2}(?:\.\d+)?\.[^/]+$",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_ ](\d{2})")
RE_BOCM = re.compile(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    m = RE_BOCM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_name(url: str) -> str:
    return unescape(urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name))


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "pgou" in n or "pgouc" in n:
        if "memoria" in n:
            return "memoria planeamiento"
        if "planos" in n or "plano" in n or "_pl-" in n:
            return "planos ordenación"
        if "ambient" in n or "die" in n:
            return "documentación ambiental"
        return "planeamiento"
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "bocm" in n:
        return "publicación BOCM"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "convenio" in n:
        return "convenio urbanístico"
    if "informacion publica" in n or "información pública" in n:
        return "información pública"
    if "licencia" in n:
        return "modelo licencia"
    if "declaraci" in n:
        return "declaración responsable"
    return "documento urbanismo"


class CercedillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (urbanismo + PGOU + anuncios PDF) + SITCM WFS (ámbitos CM)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.anuncios_url = str(self.config.get("anuncios_url") or ANUNCIOS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cercedilla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cercedilla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str, base: str = WEB_BASE) -> str:
        return urllib.parse.urljoin(f"{base}/", href)

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._sitcm_cache is not None:
            return self._sitcm_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{WFS_MUNICIPIO}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache = {}
            return self._sitcm_cache
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        cache = self._load_sitcm_ambitos()
        feat = cache.get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = (
            f"DS_MUNICIPIO='{WFS_MUNICIPIO}' AND "
            f"DS_NOMB_AMB='{ambit_name.replace(chr(39), chr(39) * 2)}'"
        )
        query_url = (
            f"{WFS_BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName={WFS_TYPE}"
            f"&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER={urllib.parse.quote(cql)}"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, _meta = resolve_ambito_geometry(WFS_MUNICIPIO, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": f"{WFS_BASE}?typeName={WFS_TYPE}",
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": _meta.get("ambito_name"),
            }
        title_low = (title or "").lower()
        for keyword, ambit in AMBITO_KEYWORDS:
            if keyword in title_low:
                hit = self._geometry_from_ambit(ambit)
                if hit:
                    return hit
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _extract_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = _pdf_name(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                    "url": page_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": "web_pdf",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_pdfs(html, page_url):
                pdf = rec["pdf_url"]
                if page_url == self.pgou_url and RE_PGOU_PLANO_SHEET.search(pdf):
                    continue
                if pdf not in seen:
                    seen.add(pdf)
                    rows.append(rec)
        return rows

    def _collect_anuncios_urban(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.anuncios_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = m.group(1)
            if not href.startswith("http"):
                continue
            if "cercedilla.es" not in href.lower():
                continue
            pdf = self._abs_url(href)
            name = _pdf_name(pdf)
            blob = f"{name} {pdf}"
            if not RE_ANUNCIOS_URBAN.search(blob):
                continue
            if pdf in seen:
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                    "url": self.anuncios_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": "anuncios_web",
                }
            )
        return rows

    def _collect_pgou_post(self) -> dict[str, Any] | None:
        try:
            posts = self._fetch_json(
                f"{WEB_BASE}/wp-json/wp/v2/posts?slug=avance-plan-general-ordenacion-urbana-cercedilla"
            )
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
        if not posts:
            return None
        post = posts[0]
        title = _strip_html(post.get("title", {}).get("rendered", ""))
        if not title:
            title = "Avance del Plan General de Ordenación Urbana de Cercedilla"
        fecha = (post.get("date") or "")[:10] or None
        rec = {
            "id": _stable_id("proy", self.pgou_url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": "información pública",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "pgou_avance",
        }
        self._enrich_geometry(rec)
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Departamento de Urbanismo — normativa y trámites",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Documentación y modelos de licencia",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", self.pgou_url),
                "fecha_concesion": None,
                "tipo": "planeamiento PGOU",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Avance PGOU — información pública",
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "nota": "Periodo de exposición pública del avance PGOU",
                "origen": "pgou_avance",
            },
            {
                "id": _stable_id("lic", self.anuncios_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios oficiales",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Anuncios oficiales — web municipal",
                "url": self.anuncios_url,
                "source": "ayuntamiento",
                "nota": "PDFs de anuncios y edictos",
                "origen": "anuncios_web",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación de trámites",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "eAdministración Maggioli; tablón no accesible por API",
                "origen": "sede_tramites",
            },
        ]

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        blob = f"{titulo} {row.get('pdf_url', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "modelo licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Modelo o guía de trámite; no concesión publicada",
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for doc in self._collect_seed_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "modelos": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "info": sum(1 for r in rows if r.get("origen") in ("urbanismo_web", "sede_tramites")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._collect_seed_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        add(self._collect_pgou_post())
        for doc in self._collect_seed_pdfs():
            add(self._doc_to_proyecto(doc))
        for doc in self._collect_anuncios_urban():
            add(self._doc_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_avance"),
            "web": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "anuncios": sum(1 for r in rows if r.get("origen") == "anuncios_web"),
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
