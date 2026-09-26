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

WP_BASE = "https://fresnodetorote.org"
SEDE_BASE = "https://sede.fresnodetorote.es"
MUNICIPIO = "Fresno del Torote"
ID_PREFIX = "fresno-del-torote"
WFS_MUNICIPIO = "FRESNO DE TOROTE"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

WP_CATEGORIES = (89, 41)  # urbanismo, obras-y-servicios

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ordenanzas/",
    f"{WP_BASE}/ordenanzas-municipales/",
]

DEFAULT_STATIC: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/ordenanzas/",
        "titulo": "BOCM 2024-01-22 — Incorporación de documentación (ordenanzas fiscales)",
        "fecha": "2024-01-22",
        "pdf": f"{WP_BASE}/wp-content/uploads/2025/01/BOCM-20240122-64-Incorporacion-de-Documentacion.pdf",
    },
    {
        "url": "https://idem.madrid.org/cartografia/planea/planeamiento/planeamiento/Fresno_de_Torote/Vigente/Torote_a.pdf",
        "titulo": "Plan General de Fresno de Torote — Normas Subsidiarias 1991 (IDEM)",
        "fecha": "1991-01-01",
        "pdf": "https://idem.madrid.org/cartografia/planea/planeamiento/planeamiento/Fresno_de_Torote/Vigente/Torote_a.pdf",
    },
]

AMBITO_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("ponton", "S-6 EL PONTON"),
    ("pontón", "S-6 EL PONTON"),
    ("el pobo", "AA-09 EL POBO"),
    ("serracines", "AE-10 JARDIN SARRACINES"),
    ("poligono 8", "AE-07 POLIGONO 8"),
    ("polígono 8", "AE-07 POLIGONO 8"),
    ("reguerilla", "S-5 LA REGUERILLA"),
    ("reguerillo", "AA-06 REGUERILLO"),
    ("el disco", "S-7 EL DISCO"),
    ("calvario", "S-3 EL CALVARIO"),
    ("granjilla", "S-9 LA GRANJILLA"),
    ("cirates", "S-1 LOS CIRATES UE2"),
    ("ciratos", "S-1 LOS CIRATES UE2"),
    ("fandango", "S-8 EL FANDANGO"),
    ("la dehesa", "AE-08 LA DEHESA"),
    ("pedro llorente", "AA-02 PEDRO LLORENTE"),
    ("granja avicola", "AA-05 GRANJA AVICOLA"),
    ("camarma", "AA-11 CAMINO CAMARMA"),
    ("los olmos", "AA-04 RESIDENCIAL"),
    ("residencial", "AA-04 RESIDENCIAL"),
    ("comercial", "AA-03 COMERCIAL"),
    ("aa-01", "AA-01 FRESNO"),
    ("ue1", "S-2 UE1"),
)

RE_PROYECTO = re.compile(
    r"(?i)(planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente urban|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"concentraci[oó]n parcel|parcelaria|bando.*(?:suelo|enajenaci[oó]n|parcela)|"
    r"licencia(?:s)?(?: de)? obra|estudio (?:ac[uú]stico|ambiental|de detalle)|"
    r"\baa[\.\-\s]*0?\d+\b|\bs[\.\-\s]*\d+\b|\bae[\.\-\s]*\d+\b|"
    r"bocm|suelo solidario|cesi[oó]n de parcela|proyecto de la casa|"
    r"mantenimiento de parcela|urbanizaci[oó]n|sector urban|pol[ií]gono)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(reductor(?:es)? de velocidad|alumbrado|fibra [oó]ptica|contenedor|"
    r"recogida de (?:residuos|enseres)|punto limpio|operaci[oó]n asfalto|"
    r"pista deportiva|farolas|vandalismo|corte de agua|l[ií]nea verde|"
    r"barredora|contenedores amarillos|cementerio|embellecimiento|"
    r"casa de la juventud|gimnasio|piscina|festividad|navidad|carnaval)",
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|de obra|de apertura)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|tasa.*licencia)",
)
RE_WP_PDF = re.compile(
    r'href="(https://fresnodetorote\.org/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://fresnodetorote\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{8})", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


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
    m = RE_BOCM_DATE.search(text or "")
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan parcial" in n or re.search(r"\bs-\d+\b", n):
        return "plan parcial"
    if "plan especial" in n or re.search(r"\baa-01\b", n):
        return "plan especial"
    if "estudio" in n and "detalle" in n:
        return "estudio de detalle"
    if "nnss" in n or "normas subsidiarias" in n or "plan general" in n:
        return "normas subsidiarias"
    if "bocm" in n:
        return "publicación BOCM"
    if "suelo solidario" in n:
        return "ordenanza urbanística"
    if "cesión" in n or "cesion" in n:
        return "cesión de suelo"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


class FresnoDelToroteAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + sede Maggioli ATM + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.static_items = list(self.config.get("static_items") or DEFAULT_STATIC)
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._wp_posts: list[dict[str, Any]] | None = None
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_wp(m.group(1))
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                label = Path(urllib.parse.urlparse(pdf_url).path).name
                blob = f"{label} {pdf_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "bocm" not in blob.lower() and "urban" not in blob.lower():
                        continue
                rows.append(
                    {
                        "titulo": label.replace("-", " ").replace("_", " ")[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": page_url,
                        "pdfs": [pdf_url],
                        "origen": "wp_ordenanzas",
                    }
                )
        return rows

    def _collect_wp_rest_posts(self) -> list[dict[str, Any]]:
        if self._wp_posts is not None:
            return self._wp_posts
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for cat in WP_CATEGORIES:
            page = 1
            while page <= 5:
                url = f"{self.wp_base}/wp-json/wp/v2/posts?categories={cat}&per_page=100&page={page}"
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    pid = int(post.get("id") or 0)
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                    content = str((post.get("content") or {}).get("rendered") or "")
                    blob = f"{title} {content[:8000]}"
                    if RE_EXCLUDE.search(title) and not RE_PROYECTO.search(title):
                        continue
                    if not RE_PROYECTO.search(blob):
                        continue
                    link = str(post.get("link") or "")
                    fecha = str(post.get("date") or "")[:10] or _fecha_from_blob(blob)
                    pdfs = list(dict.fromkeys(RE_WP_PDF.findall(content)))
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "pdfs": pdfs,
                            "origen": "wp_rest",
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        self._wp_posts = rows
        return rows

    def _collect_static(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.static_items:
            pdf = item.get("pdf")
            pdfs = [pdf] if pdf else []
            rows.append(
                {
                    "titulo": item["titulo"][:500],
                    "fecha": item.get("fecha") or _fecha_from_blob(item.get("url", "")),
                    "url": item["url"],
                    "pdfs": pdfs,
                    "origen": "static",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites y tablón de anuncios (Maggioli ATM)",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Presentación telemática de solicitudes urbanísticas",
                "origen": "sede",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/ordenanzas/licencias"),
                "fecha_concesion": None,
                "tipo": "ordenanza licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza — Tasa por Licencias Urbanísticas",
                "url": f"{self.wp_base}/ordenanzas/",
                "pdf_url": f"{self.wp_base}/wp-content/uploads/2023/12/16-Tasa-por-Licencias-Urbanisticas.pdf",
                "source": "ayuntamiento",
                "origen": "wp_ordenanza",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/ordenanzas/apertura"),
                "fecha_concesion": None,
                "tipo": "ordenanza licencia de apertura",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza — Licencia de Apertura de Establecimientos",
                "url": f"{self.wp_base}/ordenanzas/",
                "pdf_url": f"{self.wp_base}/wp-content/uploads/2023/12/05-Licencia-de-Apertura-de-Establecimientos.pdf",
                "source": "ayuntamiento",
                "origen": "wp_ordenanza",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/ordenanzas/primera-ocupacion"),
                "fecha_concesion": None,
                "tipo": "ordenanza primera ocupación",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza — Tasa de Primera Ocupación",
                "url": f"{self.wp_base}/ordenanzas/",
                "pdf_url": f"{self.wp_base}/wp-content/uploads/2025/01/14-TASA-DE-PRIMERA-OCUPACION.pdf",
                "source": "ayuntamiento",
                "origen": "wp_ordenanza",
            },
        ]

    def _load_sitcm_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._sitcm_cache is not None:
            return self._sitcm_cache
        muni = self.wfs_municipio.replace("'", "''")
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO ILIKE '%{muni}%'",
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
            f"DS_MUNICIPIO ILIKE '%{self.wfs_municipio}%' AND "
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
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": (
                    f"{WFS_BASE}?service=WFS&typeName={WFS_TYPE}"
                    f"&CQL_FILTER=DS_MUNICIPIO ILIKE '%{self.wfs_municipio}%'"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
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

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        cache = self._load_sitcm_ambitos()
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for name_upper, feat in cache.items():
            if len(name_upper) < 4:
                continue
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or name_upper).strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": f"{self.wp_base}/ordenanzas/",
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO ILIKE '%{self.wfs_municipio}%' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{WFS_BASE}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        pdf = row["pdfs"][0] if row.get("pdfs") else None
        key = pdf or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
        self._enrich_geometry(rec)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_seed_pdfs():
            rec = self._row_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_ordenanzas"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_seed_pdfs():
            rec = self._row_to_licencia(row)
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for row in self._collect_static():
            add(self._row_to_proyecto(row))
        for row in self._collect_seed_pdfs():
            add(self._row_to_proyecto(row))
        for row in self._collect_wp_rest_posts():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
