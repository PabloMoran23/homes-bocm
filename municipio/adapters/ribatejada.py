from __future__ import annotations

import hashlib
import json
import re
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
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://www.ribatejada.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://ribatajada.sedipualba.es"
MUNICIPIO = "Ribatejada"
ID_PREFIX = "ribatejada"

BANDOS_URL = f"{WP_BASE}/bandos-municipales/"
ORDENANZAS_URL = f"{WP_BASE}/ordenanzas/"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
TRAMITE_INSTANCIA = f"{SEDE_BASE}/carpetaciudadana/tramite.aspx?idtramite=14403"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "RIBATEJADA"

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": TRAMITE_INSTANCIA,
        "tipo": "instancia general",
        "titulo": "Registro electrónico / presentación instancia general",
    },
    {
        "url": TABLON_URL,
        "tipo": "tablón de anuncios",
        "titulo": "Tablón de anuncios electrónico — sede sedipualba",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|instancia general)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"modificaci[oó]n|sector|parcela|suelo|urbanizaci[oó]n|bocm|ordenanza|"
    r"\b(?:ue|ua|ad|an|ai|pau|sau)-\d+\b|unidad de actuaci[oó]n|pol[ií]gono industrial)",
)
RE_SKIP = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|convocatoria.*plaza|"
    r"cobranza|basura|veh[ií]culo|ivtm|iae\b|ibi\b|igualdad|fiestas|mercadillo|"
    r"incendio|invernal|antivectorial|puertas abiertas|proceso de admisi[oó]n|"
    r"lista (?:provisional|definitiva)|tribunal|administrativo)",
)
RE_WP_LINK = re.compile(rf'href="({re.escape(WP_BASE)}/[^"#?]+)"', re.I)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM[-_]?(\d{4})(\d{2})(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UE|UA|AD|AN|AI|PAU|SAU|S)-\d+[A-Z0-9-]*)\b")


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
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
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
    except (TypeError, ValueError, OverflowError):
        return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = re.search(r"/(\d{4})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(urllib.parse.unquote(url)).name.replace("-", " "))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bua-\d+\b", n):
        return "unidad de actuación"
    if "polígono industrial" in n or "poligono industrial" in n:
        return "polígono industrial"
    if "paraje" in n:
        return "ámbito urbanístico"
    if "bocm" in n or "aprobación inicial" in n or "aprobacion inicial" in n:
        return "aprobación inicial"
    if "ordenanza" in n:
        return "ordenanza municipal"
    if "informaci" in n:
        return "información pública"
    if "sitcm" in n:
        return "planeamiento"
    return "urbanismo"


def _abs_url(href: str, base: str = WP_BASE) -> str:
    href = unescape(href).replace("&amp;", "&").strip()
    return urllib.parse.urljoin(f"{base}/", href)


class RibatejadaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress BeTheme + sede sedipualba + ámbitos SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.bandos_url = str(self.config.get("bandos_url") or BANDOS_URL)
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._sitcm_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, charset: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ribatejada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return raw.decode(enc, errors="replace")

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
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{self.wfs_municipio}'",
            }
        )
        url = f"{self.wfs_url}?{params}"
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
        feat = self._load_sitcm_ambitos().get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        esc = ambit_name.replace("'", "''")
        cql = f"DS_MUNICIPIO='{self.wfs_municipio}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "5",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?{params}",
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        title_up = title.upper()
        for ambit_name in self._load_sitcm_ambitos():
            compact_title = re.sub(r"[\s\-]+", "", title_up)
            compact_ambit = re.sub(r"[\s\-]+", "", ambit_name)
            if compact_ambit in compact_title or compact_title in compact_ambit:
                return self._geometry_from_ambit(ambit_name)
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_sitcm_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ambit_name in sorted(self._load_sitcm_ambitos()):
            feat = self._load_sitcm_ambitos()[ambit_name]
            merged = _merge_geometries([feat])
            if not merged:
                continue
            titulo = f"Ámbito planeamiento SITCM — {ambit_name}"
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"sitcm-{ambit_name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": None,
                "tipo": _proyecto_tipo(ambit_name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_ambito",
            }
            geom = self._geometry_from_ambit(ambit_name)
            if geom:
                row.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    row["lat"], row["lon"] = centroid
            rows.append(row)
        return rows

    def _collect_ordenanzas_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ordenanzas_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = _abs_url(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.unquote(pdf_url)).stem.replace("-", " ")
            blob = f"{name} {pdf_url}"
            if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            row: dict[str, Any] = {
                "id": _stable_id("proy", pdf_url),
                "municipio": MUNICIPIO,
                "titulo": name[:500],
                "fecha": _fecha_from_pdf_url(pdf_url),
                "tipo": _proyecto_tipo(name),
                "url": self.ordenanzas_url,
                "pdf_url": pdf_url,
                "source": "ayuntamiento",
                "origen": "ordenanzas_pdf",
            }
            self._attach_geometry(row)
            rows.append(row)
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{WP_API}/posts?per_page=100&page={page}"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                if not isinstance(post, dict):
                    continue
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                link = str(post.get("link") or "")
                excerpt = _strip_html(str((post.get("excerpt") or {}).get("rendered") or ""))
                blob = f"{title} {excerpt}"
                if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                row: dict[str, Any] = {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _iso_date_wp(str(post.get("date") or "")),
                    "tipo": _proyecto_tipo(title),
                    "url": link,
                    "source": "ayuntamiento",
                    "origen": "wp_post",
                }
                self._attach_geometry(row)
                rows.append(row)
            if len(posts) < 100:
                break
            page += 1
        return rows

    def _collect_bandos_links(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.bandos_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_LINK.finditer(html):
            link = m.group(1).rstrip("/") + "/"
            if link in seen or "/bandos-municipales" in link:
                continue
            if any(x in link for x in ("/wp-content/", "/wp-json/", "/feed/", "/comments/")):
                continue
            seen.add(link)
            slug = link.rstrip("/").rsplit("/", 1)[-1]
            title = slug.replace("-", " ")
            blob = title
            if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            row: dict[str, Any] = {
                "id": _stable_id("proy", link),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": _parse_fecha_dmy(slug),
                "tipo": _proyecto_tipo(title),
                "url": link,
                "source": "ayuntamiento",
                "origen": "bandos_wp",
            }
            self._attach_geometry(row)
            rows.append(row)
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(self.tablon_rss, charset="iso-8859-1")
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = _strip_html(item.findtext("description") or "")
            pub = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or title.lower().startswith("no hay anuncios"):
                continue
            blob = f"{title} {desc}"
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": pub,
                    "url": link or self.tablon_url,
                    "descripcion": desc,
                    "blob": blob,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / autorización (anuncio)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES:
            url = str(item["url"])
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo; no concesión publicada",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info()
        seen = {r["id"] for r in rows}
        for item in self._collect_tablon_rss():
            lic = self._tablon_to_licencia(item)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento", "at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in (
            self._collect_sitcm_proyectos()
            + self._collect_ordenanzas_pdfs()
            + self._collect_wp_posts()
            + self._collect_bandos_links()
        ):
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)
        for item in self._collect_tablon_rss():
            proy = self._tablon_to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
