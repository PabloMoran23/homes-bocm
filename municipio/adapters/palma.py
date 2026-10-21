from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://palma.sedipualba.es"
LIFERAY_BASE = "https://seuelectronica.palma.cat"
WEB_BASE = "https://www.palma.es"
URBANISME_BASE = "https://urbanisme.palma.es"
MUNICIPIO = "Palma"
ID_PREFIX = "palma"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URBANISMO = f"{SEDE_BASE}/catalogoservicios.aspx?area=1551"
LIFERAY_URBANISMO = f"{LIFERAY_BASE}/es/urbanismo?categoryId=40315"
TABLON_LIFERAY = f"{LIFERAY_BASE}/-/tauler-electr%C3%B2nic-d-edictes-i-anuncis"

WFS_URL = "https://geoportal.palma.es/geoserver/space/ows"
WFS_LAYER = "space:INFRCATALOGOPGOU2021"

DEFAULT_LIFERAY_TRAMITES: list[dict[str, str]] = [
    {"titulo": "Obras.01 - Comunicación previa", "url": f"{LIFERAY_BASE}/-/obras.01-comunicaci%C3%B3n-previa-", "kind": "licencia"},
    {"titulo": "Obras.02 - Licencia urbanística", "url": f"{LIFERAY_BASE}/-/obras.02-licencia-urban%C3%ADstica", "kind": "licencia"},
    {"titulo": "Obras.05 - Proyecto de ejecución de una licencia urbanística", "url": f"{LIFERAY_BASE}/-/obras.05-proyecto-de-ejecuci%C3%B3n-de-una-licencia-urban%C3%ADstica", "kind": "licencia"},
    {"titulo": "Obras.08 - Licencia de primera ocupación", "url": f"{LIFERAY_BASE}/-/obras.08-licencia-de-primera-ocupaci%C3%B3n", "kind": "licencia"},
    {"titulo": "Obras.09 - Licencia urbanística para legalización", "url": f"{LIFERAY_BASE}/-/obras.09-licencia-urban%C3%ADstica-para-legalizaci%C3%B3n", "kind": "licencia"},
    {"titulo": "Planeamiento.04 - Estudio de detalle a iniciativa privada", "url": f"{LIFERAY_BASE}/-/planeamiento.04-estudio-de-detalle-a-iniciativa-privada", "kind": "proyecto"},
    {"titulo": "Planeamiento.07 - Plan especial a iniciativa privada", "url": f"{LIFERAY_BASE}/-/planeamiento.07-plan-especial-a-iniciativa-privada", "kind": "proyecto"},
    {"titulo": "Planeamiento.08 - Plan parcial a iniciativa privada", "url": f"{LIFERAY_BASE}/-/planeamiento.08-plan-parcial-a-iniciativa-privada", "kind": "proyecto"},
    {"titulo": "Planeamiento.09 - Segregación rústica a iniciativa privada", "url": f"{LIFERAY_BASE}/-/planejament.09-segregaci%C3%B3-r%C3%BAstica-a-iniciativa-privada", "kind": "proyecto"},
    {"titulo": "Gestión.08 - Proyecto de Urbanización", "url": f"{LIFERAY_BASE}/-/gesti%C3%B3n.08-proyecto-de-urbanizaci%C3%B3n", "kind": "proyecto"},
    {"titulo": "Información urb.01 - Informe consulta urbanística", "url": f"{LIFERAY_BASE}/-/informaci%C3%B3n-urb.01-informe-sobre-consulta-urban%C3%ADstica-o-certificado-de-aprovechamiento-urban%C3%ADstico", "kind": "proyecto"},
]

DEFAULT_WEB_SEEDS: list[dict[str, str]] = [
    {"titulo": "Visor de Urbanismo — Ajuntament de Palma", "url": f"{WEB_BASE}/visor-d-urbanisme"},
    {"titulo": "Departament de Planejament — urbanisme.palma.es", "url": f"{URBANISME_BASE}/planejament1"},
    {"titulo": "SIGDU — Servicio de Innovación y Gestión de Datos de Urbanismo", "url": f"{URBANISME_BASE}/-/bienvenidos-al-servicio-de-innovaci%C3%B3n-y-gesti%C3%B3n-de-datos-de-urbanismo-sigdu-1"},
    {"titulo": "Tablón electrónico de edictos y anuncios — sede Liferay", "url": TABLON_LIFERAY},
    {"titulo": "Planeamiento — sede electrónica (categoría urbanismo)", "url": LIFERAY_URBANISMO},
]

RE_LIFERAY_LINK = re.compile(
    r'href="(https://seuelectronica\.palma\.(?:cat|es)/-/[^"#?]+)"',
    re.I,
)
RE_TRAMITE_SEDIPUALBA = re.compile(
    r'href="(https://palma\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>([^<]+)',
    re.I,
)
RE_TABLON_ROW = re.compile(
    r'anuncio\.aspx\?id=(\d+)"[^>]*>.*?lblFecha">([^<]+)</span>.*?<td>\s*([^<]+?)\s*</td>',
    re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor)|autoritzaci[oó]|inicio de obra|"
    r"legalizaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|projecte|modificaci[oó]n|reparcel|"
    r"segregaci[oó]|expropi|estudi(?:o)? de detall|sector|unitat d.actuaci|"
    r"urbanitz|visor|sigdu|gesti[oó] urban|disciplina|edifici|obres\.)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|personal|empleo p[uú]blico|convocat[oò]ria.*ple|"
    r"multes|atib|subhasta|junta de govern|acords adoptats|nombrament comissi[oó])",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan parcial" in n or "planeamiento.08" in n:
        return "plan parcial"
    if "plan especial" in n or "planeamiento.07" in n:
        return "plan especial"
    if "estudio de detalle" in n or "planeamiento.04" in n:
        return "estudio de detalle"
    if "segregaci" in n:
        return "segregación rústica"
    if "urbanizaci" in n:
        return "proyecto de urbanización"
    if "visor" in n or "sigdu" in n:
        return "visor / cartografía urbanística"
    if "pgou" in n or "pla general" in n or "plan general" in n:
        return "plan general"
    if "licencia" in n or "comunicaci" in n:
        return "trámite de obra"
    if "disciplina" in n:
        return "disciplina urbanística"
    return "planeamiento"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _geojson_from_feature(obj: dict[str, Any]) -> dict[str, Any] | None:
    geom = obj.get("geometry")
    if isinstance(geom, dict) and geom.get("type") and geom.get("coordinates"):
        return geom
    return None


class PalmaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Sedipualba (tablón RSS/HTML) + Liferay seuelectronica.palma.cat + IDE Palma WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.liferay_base = str(self.config.get("liferay_base") or LIFERAY_BASE).rstrip("/")
        self.insecure_ssl = bool(self.config.get("insecure_ssl", True))
        self.liferay_tramites = list(self.config.get("liferay_tramites") or DEFAULT_LIFERAY_TRAMITES)
        self.web_seeds = list(self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)
        self._ssl_ctx: ssl.SSLContext | None = None
        if self.insecure_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl_ctx = ctx
        self._wfs_catalog: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 45, retries: int = 3) -> str:
        last_err: Exception | None = None
        host = urllib.parse.urlparse(url).netloc
        use_insecure = self._ssl_ctx is not None and (
            host.endswith("palma.cat")
            or host.endswith("palma.es")
            or "geoportal.palma" in host
        )
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-palma/1.0")},
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=timeout, context=self._ssl_ctx if use_insecure else None
                ) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.4 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_bytes(self, url: str, *, timeout: int = 45) -> bytes:
        time.sleep(self.delay_s)
        host = urllib.parse.urlparse(url).netloc
        use_insecure = self._ssl_ctx is not None and "geoportal.palma" in host
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-palma/1.0")},
        )
        with urllib.request.urlopen(
            req, timeout=timeout, context=self._ssl_ctx if use_insecure else None
        ) as resp:
            return resp.read()

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

    def _collect_sedipualba_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for catalog_url in (CATALOGO_URBANISMO, f"{self.sede_base}/catalogoservicios.aspx", f"{self.sede_base}/"):
            try:
                html = self._fetch(catalog_url, timeout=30)
            except urllib.error.URLError:
                continue
            for href, title in RE_TRAMITE_SEDIPUALBA.findall(html):
                if href in seen:
                    continue
                seen.add(href)
                rows.append({"titulo": _clean(title), "url": href, "origen": "sedipualba_tramite"})
        return rows

    def _collect_liferay_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(LIFERAY_URBANISMO, timeout=12)
            for href in RE_LIFERAY_LINK.findall(html):
                if href in seen:
                    continue
                seen.add(href)
                slug_part = href.rsplit("/-/", 1)[-1].split("/")[0]
                titulo = slug_part.replace("-", " ").title()
                rows.append({"titulo": titulo, "url": href, "origen": "liferay_crawl"})
        except urllib.error.URLError:
            pass
        for item in self.liferay_tramites:
            url = item["url"]
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": item["titulo"],
                    "url": url,
                    "origen": "liferay_seed",
                    "kind": item.get("kind"),
                }
            )
        return rows

    def _collect_web_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.web_seeds:
            rows.append(
                {
                    "titulo": seed["titulo"],
                    "url": seed["url"],
                    "origen": "web_semilla",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(f"{self.sede_base}/tablondeanuncios/tablon_rss.aspx", timeout=30)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if title and link:
                rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _collect_tablon_html(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, timeout=30)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            anuncio_id, fechas, title = m.group(1), _clean(m.group(2)), _clean(m.group(3))
            fecha = _parse_fecha_dmy(fechas.split("-")[0].strip())
            url = f"{self.sede_base}/tablondeanuncios/anuncio.aspx?id={anuncio_id}"
            rows.append(
                {
                    "titulo": title,
                    "url": url,
                    "fecha": fecha,
                    "origen": "tablon_html",
                }
            )
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": WFS_LAYER,
                "count": "100",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "startIndex": str(start),
            }
        )
        return f"{WFS_URL}?{params}"

    def _collect_wfs_catalog(self) -> list[dict[str, Any]]:
        if self._wfs_catalog is not None:
            return self._wfs_catalog
        rows: list[dict[str, Any]] = []
        start = 0
        while start < 2000:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch_bytes(url, timeout=12)
                data = json.loads(raw.decode("utf-8", errors="replace"))
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                break
            features = data.get("features") or []
            if not features:
                break
            for feat in features:
                props = feat.get("properties") or {}
                titulo = _clean(
                    str(
                        props.get("NOMBRE")
                        or props.get("nombre")
                        or props.get("DESCRIPCION")
                        or props.get("descripcion")
                        or props.get("CODIGO")
                        or props.get("codigo")
                        or "Elemento catálogo PGOU 2021"
                    )
                )
                geom = _geojson_from_feature(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": url,
                    "tipo": "catálogo PGOU 2021",
                    "origen": "ide_palma_wfs",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            if len(features) < 100:
                break
            start += 100
        self._wfs_catalog = rows
        return rows

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        kind = row.get("kind")
        if kind != "licencia" and not RE_LICENCIA.search(blob):
            return None
        if kind == "proyecto":
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia / obra",
            "distrito": None,
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa sede; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        if not record_geometry(rec):
            self._attach_wfs_by_title(rec)
        return rec

    def _attach_wfs_by_title(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        title = (rec.get("titulo") or "").lower()
        for item in self._collect_wfs_catalog():
            if not item.get("geom_geojson"):
                continue
            if title and title[:12] in (item.get("titulo") or "").lower():
                for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
                    if item.get(key) is not None:
                        rec[key] = item[key]
                return

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        kind = row.get("kind")
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if kind == "licencia":
            return None
        if kind == "proyecto" or row.get("origen") in ("web_semilla", "ide_palma_wfs"):
            return self._to_proyecto(row)
        if RE_PROYECTO.search(blob):
            return self._to_proyecto(row)
        return None

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_NOISE.search(row["titulo"]) and not RE_PROYECTO.search(row["titulo"]):
            return None
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_sedipualba_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_liferay_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss() + self._collect_tablon_html():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sedipualba_liferay_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_wfs_catalog():
            add(self._to_proyecto(item))
        for item in self._collect_web_seeds():
            add(self._row_to_proyecto(item))
        for item in self._collect_liferay_tramites():
            add(self._row_to_proyecto(item))
        for item in self._collect_sedipualba_tramites():
            add(self._row_to_proyecto(item))
        for item in self._collect_tablon_rss() + self._collect_tablon_html():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "wfs": sum(1 for r in rows if r.get("origen") == "ide_palma_wfs"),
            "liferay": sum(1 for r in rows if str(r.get("origen", "")).startswith("liferay")),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
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
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": result.get("with_geometry", 0),
        }
