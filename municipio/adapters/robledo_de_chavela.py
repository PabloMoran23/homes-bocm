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

WP_BASE = "https://robledodechavela.es"
SEDE_EADMIN = "https://robledodechavela.eadministracion.es"
SEDE_LEGACY = "https://robledodechavela.sedelectronica.es"
MUNICIPIO = "Robledo de Chavela"
ID_PREFIX = "robledo-de-chavela"
WFS_MUNICIPIO = "ROBLEDO DE CHAVELA"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

AMBITO_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("canopus", "UA-15 CANOPUS"),
    ("suiza", "UA-12 LA SUIZA ESPAÑOLA 1ª FASE"),
    ("doctor pérez", "UA-0 DOCTOR PÉREZ SUÁREZ"),
    ("doctor perez", "UA-0 DOCTOR PÉREZ SUÁREZ"),
    ("pérez suárez", "UA-0 DOCTOR PÉREZ SUÁREZ"),
    ("perez suarez", "UA-0 DOCTOR PÉREZ SUÁREZ"),
    ("arqueta", "S-II LA ARQUETA"),
    ("navahonda", "S-IV VIRGEN DE NAVAHONDA"),
    ("elisadero", "S-V ELISADERO"),
    ("el pinar", "S-VI EL PINAR"),
    ("villalba", "UA-6 VILLALBA"),
    ("zona industrial", "UA-11 ZONA INDUSTRIAL"),
    ("los prados", "UA-1 LOS PRADOS"),
    ("ensanche este", "UA-8 ENSANCHE ESTE"),
)

DEFAULT_STATIC_PDFS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/wp-content/uploads/2024/03/20240327_Otros_BOCM-20240326-49-Informacion-publica-aprobacion-inicial.pdf",
        "titulo": "BOCM 2024-03-26 — Información pública aprobación inicial",
    },
]

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/catastro/",
    f"{WP_BASE}/servicios-municipales/",
]

RE_PROYECTO = re.compile(
    r"(?i)(planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente urban|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"entidad(?:es)? urban|bando.*(?:suelo|enajenaci[oó]n|parcela|subasta)|"
    r"licencia(?:s)?(?: de)? obra|nnss|normas subsidiarias|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|\bua-\d+\b|\bue-\d+\b|"
    r"disoluci[oó]n.*entidad|bocm|monteagudillo|canopus|suiza espa|arqueta|"
    r"redacci[oó]n del plan|subasta.*parcela|sector urban|montes p[uú]blicos)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(campamento urbano|casco urbano|miriam urbano|ornitol[oó]gica|h[ií]pica|"
    r"bendici[oó]n|festividad|calendario|interurban|mapa concesional|"
    r"hosteler[ií]a|nochevieja|cine |teatro|fiesta|decoraci[oó]n navide|"
    r"visita ornitol|curso escolar|horario autob)",
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|de obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"bando.*suelo urbano)",
)
RE_LOC = re.compile(r"<loc>([^<]+)</loc>")
RE_TITLE = re.compile(r'<h1[^>]*class="entry-title"[^>]*>(.*?)</h1>', re.I | re.S)
RE_DATE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
RE_WP_PDF = re.compile(
    r'href="(https://robledodechavela\.es/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM[- ]?(\d{4})[- ](\d{2})[- ](\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "bando" in n and ("enajenaci" in n or "subasta" in n or "parcela" in n):
        return "subasta parcela"
    if "bando" in n and "suelo urbano" in n:
        return "ordenanza urbanística"
    if "pgou" in n or "plan general" in n:
        return "planeamiento"
    if "entidad" in n and "urban" in n:
        return "entidad urbanística"
    if "monteagudillo" in n or "montes" in n:
        return "información pública"
    if "canopus" in n or "suiza" in n:
        return "urbanismo"
    if "bocm" in n:
        return "publicación BOCM"
    return "urbanismo"


class RobledoDeChavelaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (bandos / información pública) + sede eAdmin Maggioli + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.sede_legacy = str(self.config.get("sede_legacy") or SEDE_LEGACY).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.static_pdfs = list(self.config.get("static_pdfs") or DEFAULT_STATIC_PDFS)
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._sitemap_urls: list[str] | None = None
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _sitemap_post_urls(self) -> list[str]:
        if self._sitemap_urls is not None:
            return self._sitemap_urls
        urls: list[str] = []
        for i in range(1, 8):
            try:
                xml = self._fetch(f"{WP_BASE}/post-sitemap{i}.xml")
            except urllib.error.URLError:
                continue
            urls.extend(RE_LOC.findall(xml))
        self._sitemap_urls = urls
        return urls

    def _post_candidate(self, url: str) -> bool:
        slug = url.rstrip("/").split("/")[-1].replace("-", " ")
        if any(k in slug for k in ("informacion", "bando", "expediente", "publica", "urban")):
            return True
        return bool(RE_PROYECTO.search(slug))

    def _parse_post_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        title_m = RE_TITLE.search(html)
        title = _strip_html(title_m.group(1)) if title_m else url.rstrip("/").split("/")[-1]
        if RE_EXCLUDE.search(title):
            return None

        blob = f"{title} {html[:15000]}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(title):
            return None

        date_m = RE_DATE.search(html)
        fecha = date_m.group(1)[:10] if date_m else _fecha_from_blob(url)
        pdfs = list(dict.fromkeys(RE_WP_PDF.findall(html)))
        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "pdfs": pdfs,
            "origen": "wp_post",
        }

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for url in self._sitemap_post_urls():
            if not self._post_candidate(url):
                continue
            rec = self._parse_post_page(url)
            if not rec or rec["url"] in seen_urls:
                continue
            seen_urls.add(rec["url"])
            rows.append(rec)
        return rows

    def _collect_static_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.static_pdfs:
            pdf = item["url"]
            titulo = item["titulo"]
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(pdf) or _fecha_from_blob(titulo),
                    "url": pdf,
                    "pdfs": [pdf],
                    "origen": "static_pdf",
                }
            )
        rows.append(
            {
                "titulo": "Redacción del Plan General de Robledo de Chavela (contratación pública)",
                "fecha": "2023-06-08",
                "url": "https://contrataciondelestado.es/wps/poc?uri=deeplink%3Adetalle_licitacion&idEvl=vqp2a1To%2B15Whbmkna2nXQ%3D%3D",
                "pdfs": [],
                "origen": "contratacion_publica",
            }
        )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.sede_eadmin}/home"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites y tablón de anuncios",
                "url": f"{self.sede_eadmin}/home",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes urbanísticas (Maggioli SPA)",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", f"{self.sede_legacy}/dossier.55"),
                "fecha_concesion": None,
                "tipo": "sede electrónica legacy",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica legacy — expediente urbanismo",
                "url": f"{self.sede_legacy}/dossier.55",
                "source": "ayuntamiento",
                "nota": "Sede espublico histórica (actualmente inactiva)",
                "origen": "sede_legacy",
            },
            {
                "id": _stable_id("lic", f"{WP_BASE}/bando-uso-de-barbacoas-en-suelo-urbano-2025/"),
                "fecha_concesion": "2025-07-01",
                "tipo": "ordenanza uso suelo urbano",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Bando — uso de barbacoas en suelo urbano 2025",
                "url": f"{WP_BASE}/bando-uso-de-barbacoas-en-suelo-urbano-2025/",
                "source": "ayuntamiento",
                "origen": "bando_web",
            },
        ]

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

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
                "CQL_FILTER": f"DS_MUNICIPIO='{self.wfs_municipio}'",
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
            f"DS_MUNICIPIO='{self.wfs_municipio}' AND "
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
                    "https://idem.comunidad.madrid/geoserver3/ows"
                    f"?service=WFS&typeName={WFS_TYPE}&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
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
        for row in self._collect_wp_posts():
            rec = self._row_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_bando"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_wp_posts():
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

        for row in self._collect_static_pdfs():
            add(self._row_to_proyecto(row))
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_post"),
            "static": sum(1 for r in rows if r.get("origen") in ("static_pdf", "contratacion_publica")),
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
