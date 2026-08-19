from __future__ import annotations

import hashlib
import http.cookiejar
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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://rozasdepuertoreal.es"
SEDE_BASE = "https://sederozasdepuertoreal.eadministracion.es"
TRANSP_BASE = "https://transparenciarozasdepuertoreal.eadministracion.es"
MUNICIPIO = "Rozas de Puerto Real"
ID_PREFIX = "rozas-de-puerto-real"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "ROZAS DE PUERTO REAL"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
TABLON_URL = f"{SEDE_BASE}/PortalCiudadano/Tablon/wfrTablon.aspx"

DEFAULT_LICENCIA_DOCS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/documents/solicitud-licencia-urbanistica/",
        "titulo": "Solicitud licencia urbanística",
        "tipo": "solicitud licencia urbanística",
        "pdf": f"{WP_BASE}/wp-content/uploads/2022/12/SOLICITUD-LICENCIA-URBANISTICA.pdf",
    },
    {
        "url": f"{WP_BASE}/documents/declaracion-responsable-urbanistica/",
        "titulo": "Declaración responsable urbanística",
        "tipo": "declaración responsable urbanística",
        "pdf": f"{WP_BASE}/wp-content/uploads/2022/12/DECLARACION-RESPONSABLE-URBANISTICA.pdf",
    },
    {
        "url": f"{WP_BASE}/documents/solicitud-licencia-de-apertura/",
        "titulo": "Solicitud licencia de apertura",
        "tipo": "licencia de apertura",
    },
    {
        "url": f"{WP_BASE}/documents/solicitud-de-vado-permanente-entrada-y-salida-de-vehiculos/",
        "titulo": "Solicitud vado permanente",
        "tipo": "autorización vado",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"vado|apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|parcela|vpo|vivienda|inmobiliario|estudio de detalle|"
    r"\bua[\.\-\s]*[a-g]\b|bocm)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"fiestas|carnaval|trail|pleno municipal|tractor|caminos rurales|"
    r"facebook|turismo|deporte|corrida|rejones|copa chenel)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\bUA[\.\-\s]*([A-G])\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_WP_TITLE = re.compile(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
RE_WP_DATE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
RE_TABLON_ROW = re.compile(r'class="dxgvDataRow[^"]*">(.*?)</tr>', re.S | re.I)


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


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href).replace("&amp;", "&"))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bua[\.\-\s]*[a-g]\b", n):
        return "unidad de actuación"
    if "vpo" in n or "vivienda joven" in n or "inmobiliario" in n:
        return "plan de vivienda"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "informaci" in n:
        return "información pública"
    if "planeamiento" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


class RozasDePuertoRealAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress LivingStore + sede eAdmin ATM + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._wp_urls_cache: list[str] | None = None
        self._sede_warmed = False

    def _fetch(self, url: str, *, referer: str | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-rozas-de-puerto-real/1.0")}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _warm_sede(self) -> None:
        if self._sede_warmed:
            return
        try:
            self._fetch(f"{self.sede_base}/PortalCiudadano/Menus/wfrBienvenida.aspx")
            self._sede_warmed = True
        except urllib.error.URLError:
            pass

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
            if name:
                cache[name.upper()] = f
                code_m = RE_AMBIT_CODE.search(name)
                if code_m:
                    cache[f"UA-{code_m.group(1).upper()}"] = f
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
            feat = cache.get(f"UA-{m.group(1).upper()}")
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
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            docu = str(props.get("DS_DOCU") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            if docu:
                titulo = f"{titulo} ({docu})"
            merged = _merge_geometries([f])
            fecha = None
            fc_bocm = props.get("FC_BOCM")
            if fc_bocm:
                fecha = str(fc_bocm)[:10]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
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

    def _collect_tablon(self) -> list[dict[str, Any]]:
        self._warm_sede()
        try:
            html = self._fetch(self.tablon_url, referer=f"{self.sede_base}/")
        except urllib.error.URLError:
            return []
        if "NO DISPONIBLE" in html or "dxgvDataRow" not in html:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)
            texts = [_strip_html(c) for c in cells]
            texts = [t for t in texts if t and "Cargando" not in t]
            if len(texts) >= 2:
                fecha = _parse_fecha_dmy(texts[0])
                titulo = texts[1]
            else:
                raw = _strip_html(m.group(1))
                fecha = _parse_fecha_dmy(raw)
                titulo = raw
                if fecha:
                    titulo = raw.replace(fecha, "", 1).strip()
            if not titulo or len(titulo) < 5:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": self.tablon_url,
                    "origen": "tablon_sede",
                    "blob": titulo,
                }
            )
        return rows

    def _wp_post_urls(self) -> list[str]:
        if self._wp_urls_cache is not None:
            return self._wp_urls_cache
        try:
            xml = self._fetch(f"{self.wp_base}/post-sitemap.xml")
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
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(title):
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
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "id": _stable_id("lic", f"{self.sede_base}/PortalCiudadano/Menus/wfrBienvenida.aspx"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites y tablón de anuncios",
                "url": f"{self.sede_base}/PortalCiudadano/Menus/wfrBienvenida.aspx",
                "source": "ayuntamiento",
                "nota": "Maggioli ATM SPA; tablón en wfrTablon.aspx",
                "origen": "sede_eadmin",
            }
        )
        for doc in DEFAULT_LICENCIA_DOCS:
            rec: dict[str, Any] = {
                "id": _stable_id("lic", doc["url"]),
                "fecha_concesion": None,
                "tipo": doc["tipo"],
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": doc["titulo"],
                "url": doc["url"],
                "source": "ayuntamiento",
                "origen": "wp_documento",
            }
            if doc.get("pdf"):
                rec["pdf_url"] = doc["pdf"]
            rows.append(rec)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or self.wp_base,
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
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("url") or blob),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row.get("url") or self.tablon_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_tablon():
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
        for row in self._collect_tablon():
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
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))
        for row in self._collect_tablon():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
