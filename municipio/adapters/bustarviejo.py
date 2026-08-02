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

WP_BASE = "https://www.ayuntamientodebustarviejo.org"
SEDE_BASE = "https://bustarviejo.eadministracion.es"
TRANSP_BASE = "https://transparenciabustarviejo.eadministracion.es"
TRIBUTOS_BASE = "https://tributosbustarviejo.eadministracion.es"
MUNICIPIO = "Bustarviejo"
ID_PREFIX = "bustarviejo"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "BUSTARVIEJO"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

DEFAULT_TRANSPARENCIA_SEEDS: list[dict[str, str]] = [
    {
        "url": f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/urbanismo---pgou-2022",
        "titulo": "PGOU 2022 — documentación de planeamiento",
        "fecha": "2022-01-01",
        "tipo": "PGOU",
    },
    {
        "url": (
            f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/"
            "urbanismo---pgou-2022/publicacion-en-bocm-del-avance-del-plan-general"
        ),
        "titulo": "Publicación en BOCM del avance del Plan General (PGOU 2022)",
        "fecha": "2022-01-01",
        "tipo": "información pública",
    },
    {
        "url": (
            f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/"
            "enajenacion-parcelas-urbanizacion-fuente-milano"
        ),
        "titulo": "Enajenación parcelas urbanización Fuente Milano",
        "fecha": None,
        "tipo": "subasta parcela",
    },
    {
        "url": f"{TRANSP_BASE}/transparencia/tablon-de-anuncios",
        "titulo": "Publicación BOCM resolución enajenación parcela sobrante (25.04.2025)",
        "fecha": "2025-04-25",
        "tipo": "enajenación",
    },
    {
        "url": f"{TRANSP_BASE}/transparencia/tablon-de-anuncios",
        "titulo": "Resumen proyecto acerado carretera de Cabanillas",
        "fecha": None,
        "tipo": "proyecto urbanístico",
    },
    {
        "url": f"{TRANSP_BASE}/transparencia/tablon-de-anuncios",
        "titulo": "Resumen presupuesto acondicionamiento acceso, parque infantil y pista polideportiva",
        "fecha": None,
        "tipo": "proyecto urbanístico",
    },
]

DEFAULT_TRANSPARENCIA_PAGES: list[str] = [
    f"{TRANSP_BASE}/transparencia/tablon-de-anuncios",
    f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/urbanismo---pgou-2022",
    (
        f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/"
        "urbanismo---pgou-2022/publicacion-en-bocm-del-avance-del-plan-general"
    ),
    f"{TRANSP_BASE}/transparencia/tablon-de-anuncios/enajenacion-parcelas-urbanizacion-fuente-milano",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|tasa.*urban|t[ií]tulo habilitante)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|parcela|bando|enajenaci[oó]n|reserva urbana|ensanche|"
    r"estudio de detalle|acerado|acondicionamiento|fuente milano|"
    r"\bP-\d+[A-Z]?\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"activaci[oó]n profesional|igualdad|fiestas|carnaval|trail|pleno municipal|"
    r"calendario fiscal|juez de paz|mesas electorales|colonias felinas|arboleado)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b(P-\d+[A-Z]?)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_TRANSP_LINK = re.compile(
    r'href=["\']([^"\']*transparenciabustarviejo\.eadministracion\.es[^"\']*)["\']',
    re.I,
)
RE_WP_TITLE = re.compile(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
RE_WP_DATE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)


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


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href).replace("&amp;", "&"))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if re.search(r"\bp-\d+", n):
        if "reserva urbana" in n:
            return "plan parcial"
        if "ensanche" in n:
            return "estudio de detalle"
        return "ámbito planeamiento"
    if "enajenaci" in n or "subasta" in n:
        return "enajenación"
    if "informaci" in n:
        return "información pública"
    if "acerado" in n or "acondicionamiento" in n:
        return "proyecto urbanístico"
    if "planeamiento" in n:
        return "planeamiento"
    return "urbanismo"


class BustarviejoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + eAdmin sede/transparencia + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.tributos_base = str(self.config.get("tributos_base") or TRIBUTOS_BASE).rstrip("/")
        self.transp_seeds = list(self.config.get("transparencia_seeds") or DEFAULT_TRANSPARENCIA_SEEDS)
        self.transp_pages = [str(u) for u in (self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._wp_urls_cache: list[str] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-bustarviejo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _wfs_query(self, cql: str, count: int = 120) -> list[dict[str, Any]]:
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
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if geom:
            ambit = meta.get("ambito_name") or ""
            cql = (
                f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                f"AND DS_NOMB_AMB='{str(ambit).replace(chr(39), chr(39) * 2)}'"
            )
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": ambit,
            }
        cache = self._load_wfs_ambitos()
        for m in RE_AMBIT_CODE.finditer(titulo or ""):
            feat = cache.get(m.group(1).upper())
            if not feat:
                continue
            merged = _merge_geometries([feat])
            if not merged:
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "")
            cql = (
                f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
            )
            return {
                "geom_geojson": merged,
                "geometry_source": "portal_wfs",
                "geometry_source_url": (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": name,
            }
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
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

    def _collect_transparencia_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.transp_seeds:
            rec: dict[str, Any] = {
                "id": _stable_id("proy", seed["url"] + seed["titulo"]),
                "municipio": MUNICIPIO,
                "titulo": seed["titulo"][:500],
                "fecha": seed.get("fecha"),
                "tipo": seed.get("tipo") or _proyecto_tipo(seed["titulo"]),
                "url": seed["url"],
                "source": "ayuntamiento",
                "origen": "transparencia_seed",
            }
            self._enrich_geometry(rec)
            rows.append(rec)
        return rows

    def _parse_transparencia_page(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        title = _strip_html(re.search(r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S).group(1)) if re.search(
            r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S
        ) else page_url
        for m in RE_PDF_HREF.finditer(html):
            pdf = _abs_url(m.group(1), self.transp_base)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(Path(urllib.parse.urlparse(pdf).path).name)
            titulo = f"{title}: {name}"[:500]
            if RE_EXCLUDE.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _parse_fecha_dmy(titulo) or _parse_fecha_dmy(name),
                    "url": page_url,
                    "pdf_url": pdf,
                    "origen": "transparencia_pdf",
                }
            )
        for m in RE_TRANSP_LINK.finditer(html):
            link = _abs_url(m.group(1), self.transp_base)
            label = _strip_html(m.group(0))
            if link in seen or RE_EXCLUDE.search(label):
                continue
            if not RE_PROYECTO.search(label):
                continue
            seen.add(link)
            rows.append(
                {
                    "titulo": label[:500] or link,
                    "fecha": _parse_fecha_dmy(label),
                    "url": link,
                    "origen": "transparencia_link",
                }
            )
        return rows

    def _collect_transparencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.transp_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            if "Service Unavailable" in html or len(html) < 500:
                continue
            rows.extend(self._parse_transparencia_page(html, page_url))
        return rows

    def _wp_post_urls(self) -> list[str]:
        if self._wp_urls_cache is not None:
            return self._wp_urls_cache
        try:
            xml = self._fetch(f"{self.wp_base}/wp-sitemap-posts-post-1.xml")
        except urllib.error.URLError:
            self._wp_urls_cache = []
            return self._wp_urls_cache
        urls = [m.group(1) for m in re.finditer(r"<loc>([^<]+)</loc>", xml)]
        self._wp_urls_cache = urls
        return urls

    def _parse_wp_post(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        title_m = RE_WP_TITLE.search(html)
        title = _strip_html(title_m.group(1)) if title_m else url.rstrip("/").split("/")[-1]
        if RE_EXCLUDE.search(title):
            return None
        blob = f"{title} {html[:12000]}"
        if not RE_PROYECTO.search(blob):
            return None
        date_m = RE_WP_DATE.search(html)
        fecha = date_m.group(1)[:10] if date_m else _parse_fecha_dmy(blob)
        pdfs = list(dict.fromkeys(_abs_url(h, self.wp_base) for h in RE_PDF_HREF.findall(html)))
        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "pdfs": pdfs,
            "origen": "wp_post",
        }

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._wp_post_urls():
            rec = self._parse_wp_post(url)
            if rec:
                rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tasa_url = (
            f"{self.tributos_base}/CiudadaNET.jsp?g=11&nuevo=true&o=61&org=0&p=2"
        )
        return [
            {
                "id": _stable_id("lic", f"{self.sede_base}/home"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites urbanísticos",
                "url": f"{self.sede_base}/home",
                "source": "ayuntamiento",
                "nota": "Presentación telemática tras autoliquidación de tasa",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", tasa_url),
                "fecha_concesion": None,
                "tipo": "tasa servicios urbanísticos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tasa servicios urbanísticos (licencia, DR, comunicación previa)",
                "url": tasa_url,
                "source": "ayuntamiento",
                "nota": "Autoliquidación previa a solicitud en sede",
                "origen": "tributos",
            },
            {
                "id": _stable_id("lic", f"{self.transp_base}/transparencia/tablon-de-anuncios"),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — portal transparencia",
                "url": f"{self.transp_base}/transparencia/tablon-de-anuncios",
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios administrativos",
                "origen": "transparencia",
            },
        ]

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or self.transp_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        elif row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
        self._enrich_geometry(rec)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("url") or blob),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row.get("url") or self.transp_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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
        for row in self._collect_transparencia_pages():
            rec = self._row_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_transparencia_pages():
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
        for rec in self._collect_transparencia_seeds():
            add(rec)
        for row in self._collect_transparencia_pages():
            add(self._row_to_proyecto(row))
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
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
