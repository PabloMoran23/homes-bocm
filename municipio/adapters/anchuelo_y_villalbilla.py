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

WP_BASE = "https://aytoanchuelo.com"
WP_API = f"{WP_BASE}/index.php/wp-json/wp/v2"
SEDE_EADMIN = "https://sedeanchuelo.eadministracion.es"
TRANSPARENCIA_URL = "https://transparenciaanchuelo.eadministracion.es"
AVANCE_PGOU_URL = f"{WP_BASE}/index.php/avance-pgou/"
CIUDADANOS_URL = f"{WP_BASE}/index.php/ciudadanos/"
PGOU_CM_EVAL_URL = (
    "http://www.comunidad.madrid/transparencia/normativa/"
    "consultas-procedimiento-evaluacion-ambiental-estrategica-avance-plan-general-ordenacion"
)
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
MUNICIPIO = "Anchuelo"
ID_PREFIX = "anchuelo-y-villalbilla"
WFS_MUNICIPIO = "ANCHUELO"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": AVANCE_PGOU_URL,
        "titulo": "Avance PGOU — revisión Plan General de Ordenación Urbana de Anchuelo",
        "fecha": "2021-03-01",
        "tipo": "PGOU",
        "origen": "avance_pgou",
    },
    {
        "url": PGOU_CM_EVAL_URL,
        "titulo": "Consulta evaluación ambiental estratégica — avance PGOU Anchuelo (Comunidad de Madrid)",
        "fecha": "2021-03-01",
        "tipo": "información pública",
        "origen": "pgou_cm_eval",
    },
    {
        "url": SITCM_VISOR_URL,
        "titulo": "Visor cartográfico SITCM — planeamiento Comunidad de Madrid (Anchuelo UA-1..UA-9)",
        "fecha": None,
        "tipo": "planeamiento",
        "origen": "sitcm_visor",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|administrativa)|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|de avance)|"
    r"avance.*pgou|revisi[oó]n del plan|planta fotovoltaica|autorizaci[oó]n administrativa|"
    r"declaraci[oó]n de utilidad p[uú]blica|desbroce.*parcelas urban|parcelas urbanas|"
    r"instalaci[oó]n|bocm|\bua[\.\-\s]*\d+)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(interurban|l[ií]nea 275|autob[uú]s|carretera m-|corte de carretera|"
    r"fiesta|bel[eé]n viviente|cine de verano|empleo|subvenci[oó]n.*empleo|"
    r"piscina|vacunaci[oó]n|ornitol|navidad|reyes|cabalga|pleno|convocatoria sesi[oó]n|"
    r"guardia civil|5g|temperatura|contenedor marr[oó]n|mayores|juventud|"
    r"presupuesto|padron|padr[oó]n|ibi|basura.*semestre|mapa concesional)",
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
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
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
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
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "fotovoltaica" in n or "instalaci" in n:
        return "instalación energética"
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "desbroce" in n and "urban" in n:
        return "ordenanza urbanística"
    if "autorizaci" in n or "utilidad p[uú]blica" in n:
        return "autorización administrativa"
    if "sitcm" in n:
        return "planeamiento"
    return "urbanismo"


class AnchueloYVillalbillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress aytoanchuelo.com + SITCM WFS (partial). Slug cola incluye Villalbilla por artefacto BOCM."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_api = str(self.config.get("wp_api_base") or WP_API).rstrip("/")
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.transparencia_url = str(self.config.get("transparencia_url") or TRANSPARENCIA_URL)
        self.avance_pgou_url = str(self.config.get("avance_pgou_url") or AVANCE_PGOU_URL)
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for page in range(1, 8):
            url = f"{self.wp_api}/posts?per_page=100&page={page}"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            for post in batch:
                if not isinstance(post, dict):
                    continue
                link = str(post.get("link") or "")
                if not link or link in seen_links:
                    continue
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                content_html = str((post.get("content") or {}).get("rendered") or "")
                blob = f"{title} {content_html[:12000]}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(title):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                seen_links.add(link)
                pdfs = list(dict.fromkeys(RE_PDF.findall(content_html)))
                fecha = str(post.get("date") or "")[:10] or _parse_fecha_dmy(blob)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "pdfs": pdfs,
                        "origen": "wp_rest",
                        "blob": blob,
                    }
                )
            if len(batch) < 100:
                break
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.static_proyectos:
            rows.append(
                {
                    "titulo": seed["titulo"][:500],
                    "fecha": seed.get("fecha"),
                    "url": seed["url"],
                    "pdfs": [],
                    "origen": seed.get("origen", "static_seed"),
                    "tipo_hint": seed.get("tipo"),
                    "blob": seed["titulo"],
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sede_eadmin),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites urbanísticos",
                "url": self.sede_eadmin,
                "source": "ayuntamiento",
                "nota": "Maggioli eAdmin (raíz devuelve 404 en verificación remota)",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", self.transparencia_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia municipal",
                "url": self.transparencia_url,
                "source": "ayuntamiento",
                "nota": "Portal no disponible (Maggioli)",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", CIUDADANOS_URL),
                "fecha_concesion": None,
                "tipo": "trámites ciudadanos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ciudadanos — trámites y servicios municipales",
                "url": CIUDADANOS_URL,
                "source": "ayuntamiento",
                "nota": "Atención presencial urbanismo (sin formularios descargables)",
                "origen": "ciudadanos",
            },
        ]

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
                    f"{WFS_BASE}?service=WFS&typeName={WFS_TYPE}"
                    f"&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        cache = self._load_sitcm_ambitos()
        if cache and re.search(r"(?i)\bpgou\b|plan general", title or ""):
            merged = _merge_geometries(list(cache.values()))
            if merged:
                return {
                    "geom_geojson": merged,
                    "geometry_source": "portal_wfs",
                    "geometry_source_url": (
                        f"{WFS_BASE}?service=WFS&typeName={WFS_TYPE}"
                        f"&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
                    ),
                    "coord_source": "portal_geometry_centroid",
                    "ambito_sit": "PGOU (todos UA)",
                }
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

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(row.get("titulo") or ""):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        pdf = row["pdfs"][0] if row.get("pdfs") else None
        key = pdf or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo_hint") or _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
        self._enrich_geometry(rec)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        pdfs = row.get("pdfs") or []
        pdf = pdfs[0] if pdfs else None
        key = pdf or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("titulo") or ""),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": pdf or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
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

    def _collect_source_rows(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for rec in self._collect_static_proyectos():
            by_key[rec["url"]] = rec
        for rec in self._collect_wp_posts():
            by_key.setdefault(rec["url"], rec)
        return list(by_key.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_source_rows():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(self._collect_licencia_info_pages())}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_source_rows():
            rec = self._row_to_licencia(item)
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
        for item in self._collect_source_rows():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "static": sum(1 for r in rows if str(r.get("origen", "")).startswith(("avance", "pgou", "sitcm", "static"))),
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
