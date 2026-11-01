from __future__ import annotations

import hashlib
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

WP_BASE = "https://ayto-sesena.org"
SEDE_BASE = "https://sede.ayto-sesena.org/eAdmin"
MUNICIPIO = "Seseña"
ID_PREFIX = "sesena"
INE_MUN = "45161"

TABLON_DEFAULT = f"{SEDE_BASE}/Tablon.do?action=verAnuncios&tipoTablon=1"
CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)

DEFAULT_PUBLICACION_PAGES: list[str] = [
    f"{WP_BASE}/plan-de-ordenacion-municipal-en-tramite/",
    f"{WP_BASE}/transparencia/transparencia-pom/",
    f"{WP_BASE}/transparencia/transparencia-uo/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WP_BASE}/descarga-de-documentos/",
    f"{WP_BASE}/concejalia-urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|edicto.*licencia|"
    r"notificaci[oó]n.*licencia|disciplina urban|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|ordenaci)|pgou|pom|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"memoria|planos|edicto|aprobaci[oó]n|sau\s*\d|pei|urbanizaci[oó]n|"
    r"plataforma log)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./_-](\d{2})[./_-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_TABLON_LINK = re.compile(
    r'href="([^"]*Tablon\.do\?[^"]*action=verAnuncio[^"]*id=([A-F0-9]+)[^"]*)"',
    re.I,
)
RE_TABLON_DESC = re.compile(
    r"(?i)Descripci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*([^<]+)",
)
RE_TABLON_FECHA = re.compile(
    r"(?i)Fecha inicio publicaci[oó]n\s*</[^>]+>\s*</[^>]+>\s*<[^>]+>\s*"
    r"(\d{1,2}/\d{1,2}/\d{4})",
)
RE_URBAN_PDF_PATH = re.compile(
    r"(?i)(/documentos/pom/|/documentos/urbanismo/|/ayto-doc/|licencia|obra|urban)",
)


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


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r'<h1[^>]*class="[^"]*elementor-heading-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3 and "buscado" not in t.lower():
                return t[:500]
    return fallback


def _pdf_tipo(name: str, section: str = "") -> str:
    blob = f"{name} {section}".lower()
    if "sau" in blob and "urbaniz" in blob:
        return "proyecto urbanización"
    if "reparcel" in blob:
        return "reparcelación"
    if "pei" in blob:
        return "plan especial"
    if "pgou" in blob or "pom" in blob or "ordenacion" in blob or "ordenación" in blob:
        return "POM / PGOU"
    if "urbaniz" in blob:
        return "proyecto urbanización"
    if "memoria" in blob:
        return "memoria informativa"
    if "planos" in blob:
        return "documentación planos"
    return "documento urbanismo"


class SesenaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (POM/transparencia) + tablón sede eAdmin + formularios licencia + CLM ArcGIS PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_DEFAULT)
        self.publicacion_pages = [str(u) for u in (self.config.get("publicacion_pages") or DEFAULT_PUBLICACION_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or INE_MUN)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _uses_sede_ssl(self, url: str) -> bool:
        return "sede.ayto-sesena.org" in url

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sesena/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self._uses_sede_ssl(url) else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sesena/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        href = unescape(href).strip()
        if href.startswith("http://ayto-sesena.org"):
            href = "https://" + href[len("http://") :]
        return urllib.parse.urljoin(base, href)

    def _abs_sede(self, href: str) -> str:
        return self._abs_url(href, f"{self.sede_base}/")

    def _fetch_clm_pgou(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if self._pgou_geom is not None:
            return self._pgou_geom, self._pgou_meta
        where = f"COD_INE='{self.cod_ine}'"
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "NOM_PLAN,PLAN_,FECHA_APRO,DESCARGA",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
            }
        )
        url = f"{self.clm_layer}/query?{params}"
        try:
            raw = self._fetch_bytes(url, timeout=90)
            data = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        features = data.get("features") or []
        if not features:
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        feat = features[0]
        geom = feat.get("geometry")
        props = feat.get("properties") or {}
        if not isinstance(geom, dict) or not geom.get("type"):
            self._pgou_geom = None
            self._pgou_meta = None
            return None, None
        self._pgou_geom = geom
        self._pgou_meta = {
            "nom_plan": props.get("NOM_PLAN"),
            "plan_code": props.get("PLAN_"),
            "descarga": props.get("DESCARGA"),
            "geometry_source_url": url,
        }
        return self._pgou_geom, self._pgou_meta

    def _pgou_proyecto_row(self) -> dict[str, Any] | None:
        geom, meta = self._fetch_clm_pgou()
        if not geom or not meta:
            return None
        nom = str(meta.get("nom_plan") or "Plan de Ordenación Municipal")
        url = str(meta.get("descarga") or f"{WP_BASE}/plan-de-ordenacion-municipal-en-tramite/")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"clm-pgou-{self.cod_ine}"),
            "municipio": MUNICIPIO,
            "titulo": f"{nom} — {MUNICIPIO} (CLM geoportal)",
            "fecha": None,
            "tipo": "POM / PGOU",
            "url": url,
            "source": "ayuntamiento",
            "origen": "clm_arcgis",
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": meta.get("geometry_source_url"),
            "coord_source": "portal_geometry_centroid",
        }
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid
        return rec

    def _attach_pgou_if_plan(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = (rec.get("titulo") or "").lower()
        if not any(k in blob for k in ("pgou", "pom", "plan de orden", "plan general", "normas subsidiarias")):
            return
        geom, meta = self._fetch_clm_pgou()
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = (meta or {}).get("geometry_source_url")
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _extract_pdfs_with_context(self, html: str, page_url: str) -> list[dict[str, Any]]:
        page_title = _page_title(html, page_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "))
        sections: list[tuple[int, str]] = []
        for m in re.finditer(r"<h[234][^>]*>([^<]+)", html, re.I):
            sections.append((m.start(), unescape(m.group(1).strip())[:200]))
        for m in re.finditer(r"<td[^>]*>\s*([^<]{8,120})\s*</td>\s*<td", html, re.I):
            sections.append((m.start(), unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:200]))

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            if "favicon" in pdf.lower() or "icono-pdf" in pdf.lower():
                continue
            if not RE_URBAN_PDF_PATH.search(pdf) and not RE_PROYECTO.search(pdf):
                continue
            pos = m.start()
            section = page_title
            for start, title in sections:
                if start < pos:
                    section = title
                else:
                    break
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rec_id = _stable_id("proy", pdf)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            titulo = f"{section}: {name}" if section and section.lower() not in name.lower() else name
            rec: dict[str, Any] = {
                "id": rec_id,
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_pdf_url(pdf),
                "tipo": _pdf_tipo(name, section),
                "url": page_url,
                "pdf_url": pdf,
                "source": "ayuntamiento",
                "origen": "publicacion",
            }
            rows.append(rec)
        return rows

    def _collect_publicacion_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        pgou = self._pgou_proyecto_row()
        if pgou and pgou["id"] not in seen:
            seen.add(pgou["id"])
            rows.append(pgou)
        for page_url in self.publicacion_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_pdfs_with_context(html, page_url):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _parse_tablon_list(self, html: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in RE_TABLON_LINK.finditer(html):
            href, ann_id = m.group(1), m.group(2)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            items.append({"id": ann_id, "url": self._abs_sede(href)})
        if items:
            return items
        for m in re.finditer(r"verAnuncio[^\"']*id=([A-F0-9]+)", html, re.I):
            ann_id = m.group(1)
            if ann_id in seen:
                continue
            seen.add(ann_id)
            items.append(
                {"id": ann_id, "url": f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"}
            )
        return items

    def _fetch_tablon_detail(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url, use_sede_ssl=True)
        except urllib.error.URLError:
            return None
        title_m = re.search(r"<h2[^>]*>([^<]+)", html, re.I)
        title = unescape(title_m.group(1).strip()) if title_m else ""
        if not title:
            desc_m = RE_TABLON_DESC.search(html)
            title = unescape(desc_m.group(1).strip()) if desc_m else ""
        fecha_m = RE_TABLON_FECHA.search(html)
        fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else None
        pdfs = [self._abs_sede(x) for x in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, re.I)]
        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "pdf_url": pdfs[0] if pdfs else None,
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        items = self._parse_tablon_list(html)
        rows: list[dict[str, Any]] = []
        for item in items:
            detail = self._fetch_tablon_detail(item["url"])
            if detail and detail.get("titulo"):
                detail["ann_id"] = item["id"]
                rows.append(detail)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = str(row.get("titulo") or "")
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("ann_id") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = str(row.get("titulo") or "")
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("ann_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": "urbanismo",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_pgou_if_plan(rec)
        return rec

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, "Licencias urbanísticas")
            rec_id = _stable_id("lic", page_url)
            if rec_id not in seen:
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": page_title[:500],
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "tramite_info",
                        "nota": "Formularios PDF; tramitación vía sede (certificado digital)",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                if not RE_LICENCIA.search(name) and "/documentos/descargas/" not in pdf.lower():
                    continue
                if not RE_LICENCIA.search(name):
                    continue
                rid = _stable_id("lic", pdf)
                if rid in seen:
                    continue
                seen.add(rid)
                rows.append(
                    {
                        "id": rid,
                        "fecha_concesion": _fecha_from_pdf_url(pdf),
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": name[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "tramite_doc",
                    }
                )
        return rows

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
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if str(r.get("origen", "")).startswith("tramite")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias_tramites():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        for rec in self._collect_publicacion_proyectos():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "publicacion": sum(1 for r in rows if r.get("origen") in ("publicacion", "clm_arcgis")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
