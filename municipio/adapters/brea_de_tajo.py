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
from municipio.gis.sitcm import WFS_BASE, resolve_ambito_geometry

WP_BASE = "https://breadetajo.es"
SEDE_EADMIN = "https://sedebreadetajo.eadministracion.es"
SEDE_LEGACY = "https://breadetajo.sedelectronica.es"
MUNICIPIO = "Brea de Tajo"
ID_PREFIX = "brea-de-tajo"

WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "BREA DE TAJO"
SITCM_VISOR_URL = "https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=025"
MISECAM_URL = "https://misecam.org/urbanismo/"

DEFAULT_TRAMITE_PDFS: list[dict[str, str]] = [
    {
        "url": "https://www.breadetajo.es/pdf/solicitud_licencia_urbanistica.pdf",
        "tipo": "solicitud licencia urbanística",
        "titulo": "Solicitud de licencia urbanística (impreso)",
    },
    {
        "url": "https://www.breadetajo.es/pdf/declaracion_responsable.pdf",
        "tipo": "declaración responsable urbanística",
        "titulo": "Declaración responsable urbanística (impreso)",
    },
    {
        "url": "https://www.breadetajo.es/pdf/instancia_general.pdf",
        "tipo": "instancia general",
        "titulo": "Instancia general (urbanismo)",
    },
    {
        "url": "https://breadetajo.es/pdf/7_licencia_urbanistica.pdf",
        "tipo": "ordenanza licencia urbanística",
        "titulo": "Ordenanza fiscal licencia urbanística",
    },
]

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": SITCM_VISOR_URL,
        "titulo": "Visor SITCM — planeamiento urbanístico Brea de Tajo (municipio 025)",
        "fecha": "1987-11-11",
        "tipo": "visor planeamiento",
        "nota": "7 unidades de actuación (UA-1…UA-7) de Normas Subsidiarias Matriz 1987",
    },
    {
        "url": MISECAM_URL,
        "titulo": "MISECAM — Oficina Técnica de Asesoramiento Urbanístico (mancomunidad)",
        "fecha": "2023-02-01",
        "tipo": "asesoramiento urbanístico",
        "nota": "Asesoramiento técnico compartido; atención martes 12:00-14:00 con cita previa",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|de obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|ordenanza.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|misecam|bocm|"
    r"\bua-\d+\b|unidad de actuaci|matriz|visor)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|impuesto|tasa|ibi\b|ivtm|basura|residuos|"
    r"carnaval|fiesta|motos|p[aá]del|front[oó]n|bibliobus|cobranza|"
    r"calendario fiscal|coto de caza|c[aá]ritas|proyecto cgr)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b(UA-\d+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if re.search(r"\bua-\d+\b", n) or "unidad de actuaci" in n:
        return "unidad de actuación"
    if "nnss" in n or "normas subsidiarias" in n or "matriz" in n:
        return "normas subsidiarias"
    if "misecam" in n:
        return "asesoramiento urbanístico"
    if "visor" in n or "sitcm" in n:
        return "visor planeamiento"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class BreaDeTajoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (impresos) + sede eAdmin inaccesible + SITCM WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.sede_legacy = str(self.config.get("sede_legacy") or SEDE_LEGACY).rstrip("/")
        self.tramite_pdfs = list(self.config.get("tramite_pdfs") or DEFAULT_TRAMITE_PDFS)
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._wp_posts: list[dict[str, Any]] | None = None

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

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache[name.upper()] = f
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache[code_m.group(1).upper()] = f
        self._wfs_cache = cache
        return cache

    def _geometry_from_ambit(self, ambit_name: str) -> dict[str, Any] | None:
        cache = self._load_wfs_ambitos()
        feat = cache.get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' AND "
            f"DS_NOMB_AMB='{ambit_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&version=2.0.0&request=GetFeature&typeName={self.wfs_type}"
                f"&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
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
                    f"{self.wfs_url}?service=WFS&typeName={self.wfs_type}"
                    f"&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        for m in RE_AMBIT_CODE.finditer(title or ""):
            hit = self._geometry_from_ambit(m.group(1))
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
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            clas = str(props.get("DS_CLAS_SUE") or "").strip()
            docu = str(props.get("DS_DOCU") or "").strip()
            fc_bocm = str(props.get("FC_BOCM") or "")[:10] or None
            titulo = f"{name} — {docu}" if docu else name
            if clas and clas not in titulo:
                titulo = f"{titulo} ({clas})"
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fc_bocm,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", f"{self.sede_eadmin}/tablon"),
                "fecha_concesion": None,
                "tipo": "sede electrónica eAdmin",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — tablón y trámites urbanísticos",
                "url": f"{self.sede_eadmin}/PortalCiudadano/Tablon/wfrTablon.aspx",
                "source": "ayuntamiento",
                "nota": "Sede Maggioli; 502 Bad Gateway desde CI (reintentar en local)",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", f"{self.sede_legacy}/board"),
                "fecha_concesion": None,
                "tipo": "sede electrónica legacy",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede espublico legacy — temporalmente inactiva",
                "url": f"{self.sede_legacy}/board",
                "source": "ayuntamiento",
                "nota": "breadetajo.sedelectronica.es devuelve «En Construcción»",
                "origen": "sede_legacy",
            },
        ]
        for item in self.tramite_pdfs:
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "pdf_url": item["url"],
                    "source": "ayuntamiento",
                    "nota": "Impreso descargable en web municipal",
                    "origen": "wp_pdf",
                }
            )
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.static_proyectos:
            rec: dict[str, Any] = {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"][:500],
                "fecha": item.get("fecha"),
                "tipo": item.get("tipo") or _proyecto_tipo(item["titulo"]),
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "static",
            }
            if item.get("nota"):
                rec["nota"] = item["nota"]
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        if self._wp_posts is not None:
            return self._wp_posts
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{WP_BASE}/wp-json/wp/v2/posts?per_page=100&page={page}"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                if RE_EXCLUDE.search(title):
                    continue
                content = str((post.get("content") or {}).get("rendered") or "")
                blob = f"{title} {content[:4000]}"
                if not RE_PROYECTO.search(title) and not (
                    RE_PROYECTO.search(blob) and "misecam" in blob.lower()
                ):
                    continue
                link = str(post.get("link") or "")
                fecha = str(post.get("date") or "")[:10] or _parse_fecha_dmy(blob)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "origen": "wp_rest",
                    }
                )
            if len(posts) < 100:
                break
            page += 1
        self._wp_posts = rows
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_eadmin", "sede_legacy")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
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

        for rec in self._collect_static_proyectos():
            add(rec)
        for rec in self._collect_sit_ambitos():
            add(rec)
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "static": sum(1 for r in rows if r.get("origen") == "static"),
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
