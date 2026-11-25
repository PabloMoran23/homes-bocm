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

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.icv import enable_icv_compression
from municipio.http import PortalReadError, fetch_text, read_response

BASE = "https://www.ontinyent.es"
SEDE = "https://ontinyent.sedipualba.es"
MUNICIPIO = "Ontinyent"
ID_PREFIX = "ontinyent"
INE_MUN = "46184"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
TABLON_HTML = f"{SEDE}/tablondeanuncios/"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/va/pagina/territori-urbanisme-patrimoni-transport-public-serveis-municipals-activitats-autoritzacions",
    f"{BASE}/va/pagina/aprovats-definitivament-0",
    f"{BASE}/va/pagina/plans-parcials",
    f"{BASE}/va/pagina/estudis-detall",
    f"{BASE}/va/pagina/pla-general-ontinyent-2007-modificacions",
    f"{BASE}/va/pagina/pla-especial-reforma-interior-vila",
    f"{BASE}/va/pagina/pla-especial-dinfraestructura-electrica-arees-llombo-germanies",
    f"{BASE}/va/pagina/pris-clariano-llombo-almaig-germanies-raval-poble-nou",
    f"{BASE}/va/pagina/registre-programes-dactuacio",
    f"{BASE}/va/pagina/informacio-publica-0",
    f"{BASE}/va/pagina/projecte-dexpropiacio-taxacio-conjunta-lambit-del-pla-reforma-interior-del-centre-historic-raval-poble-nou-dontinyent",
    f"{BASE}/va/pagina/projecte-expropiacio-bens-afectats-ambit-ue-6-pla-especial-reforma-interior-barri-vila",
    f"{BASE}/va/pagina/projecte-expropiacio-finques-afectades-actuacio-zona-cantereria",
    f"{BASE}/va/pagina/proces-participacio-ciutadana-lestudi-dintegracio-paisatgistica-duna-installacio-solar-fotovoltaica-terme-municipal-dontinyent",
    f"{BASE}/va/pagina/projecte-durbanitzacio",
    f"{BASE}/va/pagina/urbanisme-0",
    f"{BASE}/va/pagina/ordenances-urbanistiques",
]

RE_PAGINA = re.compile(r'href="(/va/pagina/[^"#?]+)"', re.I)
RE_PDF = re.compile(r'href="(/sites/www\.ontinyent\.es/files/[^"]+\.pdf)"', re.I)
RE_TRAMITE = re.compile(
    r'href="(https://ontinyent\.sedipualba\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"\s*URBANISME\s*-\s*([^<]+)",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó] responsable|comunicaci[oó]n previa|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor)|autoritzaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pri|peri|"
    r"informaci[oó]n p[uú]blica|expedient|expropi|projecte|modificaci[oó]n|"
    r"estudi(?:s)? (?:de )?detall|reparcel|conveni|sector|ue-|sd-|programa|"
    r"participaci[oó]|reforma interior|urbanitz|parcel)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|igualtat|cultural|festiu|ve[iï]nal|musical|empadron|"
    r"compte general|matr[ií]cula iae|borsa de treball|cessi[oó] d.us)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|PE|PAI|RES)[\s\-]?(?:IND\s*)?[\dA-Z]+(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
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
    if "expropi" in n:
        return "expropiación"
    if "plan especial" in n or "peri" in n or "pri" in n:
        return "plan especial reforma interior"
    if "plan parcial" in n or "pp " in n:
        return "plan parcial"
    if "estudi" in n and "detall" in n:
        return "estudio de detalle"
    if "participaci" in n:
        return "participación pública"
    if "informaci" in n or "informació pública" in n:
        return "información pública"
    if "pgou" in n or "pla general" in n:
        return "plan general"
    if "programa" in n or "registre" in n:
        return "programa de actuación"
    if re.search(r"\b(sd|ue|sector)\b", n):
        return "sector planeamiento"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    parts = [float(x) for x in poslist.split() if x.strip()]
    if len(parts) < 6:
        return None
    coords: list[list[float]] = []
    for i in range(0, len(parts) - 1, 2):
        lat, lon = parts[i], parts[i + 1]
        coords.append([lon, lat])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class OntinyentAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal Digital Value (ontinyent.es) + sede sedipualba + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 60))
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _request(self, url: str) -> urllib.request.Request:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ontinyent/1.0")},
        )
        enable_icv_compression(req)
        return req

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        return fetch_text(self._request(url), timeout=timeout, attempts=retries, encoding="utf-8")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*[-|].*Ontinyent.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

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

    def _collect_tramites(self, *, board_unavailable: bool = False) -> list[dict[str, Any]]:
        html = self._fetch(CATALOGO_TRAMITES, timeout=12, retries=1 if board_unavailable else 2)
        rows: list[dict[str, Any]] = []
        for href, title in RE_TRAMITE.findall(html):
            rows.append(
                {
                    "titulo": _clean(f"URBANISME - {title}"),
                    "url": href,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        raw, _ = read_response(self._request(TABLON_RSS), timeout=12, attempts=2)
        channel = ET.fromstring(raw).find("channel")
        if channel is None:
            raise ValueError(f"Missing RSS channel at {TABLON_RSS}")
        rows: list[dict[str, Any]] = []
        for item in channel.findall("item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _collect_tablon_html(self) -> list[dict[str, Any]]:
        markup = self._fetch(TABLON_HTML, timeout=12, retries=1)
        board = BeautifulSoup(markup, "html.parser").select_one('div[id$="_pnlAnuncios"] table.gridview')
        if board is None:
            raise ValueError(f"Missing announcement table at {TABLON_HTML}")
        rows: list[dict[str, Any]] = []
        for line in board.select("tbody tr.clickable"):
            cells = line.find_all("td", recursive=False)
            link = line.select_one('a[href*="anuncio.aspx?id="]')
            if len(cells) != 3 or link is None:
                raise ValueError(f"Unexpected announcement row at {TABLON_HTML}")
            rows.append({
                "titulo": _clean(cells[2].get_text(" ", strip=True)),
                "url": urllib.parse.urljoin(TABLON_HTML, link["href"]),
                "fecha": _parse_fecha_dmy(cells[1].get_text(" ", strip=True)),
                "origen": "tablon_html",
            })
        if not rows:
            raise ValueError(f"No announcements in the HTML table at {TABLON_HTML}")
        return rows

    def _collect_tablon(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        unavailable = []
        for url, collect in ((TABLON_RSS, self._collect_tablon_rss), (TABLON_HTML, self._collect_tablon_html)):
            try:
                return collect(), {"status": "ok", "tablon_source": url}
            except (urllib.error.URLError, TimeoutError, PortalReadError, ET.ParseError, ValueError) as exc:
                unavailable.append({"url": url, "error": str(exc)})
        return [], {
            "status": "partial", "reason": "ontinyent_sedipualba_edicts_unavailable",
            "unavailable_sources": unavailable,
        }

    def _crawl_drupal_pages(self) -> list[dict[str, Any]]:
        queue: list[str] = list(self.seed_pages)
        seen_pages: set[str] = set()
        rows: list[dict[str, Any]] = []

        while queue and len(seen_pages) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in seen_pages:
                continue
            seen_pages.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, url.rsplit("/", 1)[-1].replace("-", " "))
            blob = f"{title} {url}"
            if RE_PROYECTO.search(blob) or any(
                k in url.lower()
                for k in (
                    "urban",
                    "plan",
                    "estudi",
                    "projecte",
                    "exprop",
                    "pri",
                    "particip",
                    "informacio-publica",
                    "registre-programes",
                )
            ):
                rows.append(
                    {
                        "titulo": title,
                        "url": url,
                        "fecha": _parse_fecha_dmy(html) or _parse_fecha_dmy(title),
                        "origen": "drupal_pagina",
                    }
                )
            for href in RE_PAGINA.findall(html):
                full = self._abs_web(href).rstrip("/")
                if full in seen_pages or full in queue:
                    continue
                low = href.lower()
                if any(
                    k in low
                    for k in (
                        "urban",
                        "plan",
                        "estudi",
                        "projecte",
                        "exprop",
                        "pri",
                        "particip",
                        "informacio-publica",
                        "registre-programes",
                        "aprovats-definitivament",
                        "ordenances-urbanistiques",
                    )
                ):
                    queue.append(full)
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": ICV_LAYER,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{ICV_WFS}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        while start < 8000:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch(url, timeout=90)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != INE_MUN:
                    continue
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob,
                    "url": url,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                    "wfs_id": fid,
                    "origen": "icv_wfs",
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
            start += 200
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa sedipualba; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in ("pp", "ue", "clasificacion", "wfs_id", "geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _drupal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "urbanisme" not in row.get("url", "").lower():
            return None
        return self._to_proyecto(row)

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

    def _collect_licencias(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        board, coverage = self._collect_tablon()
        board_unavailable = coverage["status"] == "partial"
        try:
            tramites = self._collect_tramites(board_unavailable=board_unavailable)
        except (urllib.error.URLError, TimeoutError, PortalReadError) as exc:
            coverage["status"] = "partial"
            coverage["reason"] = (
                "ontinyent_sedipualba_edicts_and_catalogue_unavailable" if board_unavailable
                else "ontinyent_sedipualba_catalogue_unavailable"
            )
            coverage.setdefault("unavailable_sources", []).append({"url": CATALOGO_TRAMITES, "error": str(exc)})
            tramites = []
        for item in tramites:
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in board:
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows, coverage

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "sede_tramites_tablon", **coverage}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_licencias()
        return self._update_rows(out_jsonl, state_path, rows, coverage)

    def _collect_proyectos(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._crawl_drupal_pages():
            add(self._drupal_to_proyecto(item))
        board, coverage = self._collect_tablon()
        for item in board:
            add(self._tablon_to_proyecto(item))
        if coverage["status"] == "partial" and not rows:
            raise ValueError("Ontinyent announcement sources are unavailable and no planning records were recovered")
        return rows, coverage

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            **coverage,
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_pagina"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon_rss", "tablon_html")),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows, coverage = self._collect_proyectos()
        return self._update_rows(out_jsonl, state_path, rows, coverage, include_geometry=True)

    def _update_rows(
        self, out_jsonl: Path, state_path: Path, rows: list[dict[str, Any]],
        coverage: dict[str, Any], *, include_geometry: bool = False,
    ) -> dict[str, Any]:
        existing = self._load_jsonl(out_jsonl)
        if coverage["status"] == "partial":
            rows = list({row["id"]: row for row in existing + rows}.values())
        self._write_jsonl(out_jsonl, rows)
        result = {"rows": len(rows), "added": max(0, len(rows) - len(existing)), **coverage}
        if include_geometry:
            result["with_geometry"] = sum(1 for row in rows if record_geometry(row))
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    **result,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
