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
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.algemesi.es"
SEDE_BASE = "https://sede.algemesi.es/eAdmin"
TRANSP_BASE = "https://transparencia.algemesi.es"
MUNICIPIO = "Algemesí"
ID_PREFIX = "algemesi"
INE_MUN = "46007"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRAMITES_CATALOG = f"{SEDE_BASE}/Registrar.do?action=inicioPortalTramites"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/va/urbanisme",
    f"{WEB_BASE}/va/seccion/urbanisme",
    f"{WEB_BASE}/va/pagina/projectes-urbans",
    f"{WEB_BASE}/va/dvmenu/2499",
    f"{TRANSP_BASE}/?page_id=185",
    f"{TRANSP_BASE}/?page_id=1003",
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, Any]] = [
    {"tipo_reg": 165, "nombre": "Sol·licitud de llicència d'obra"},
    {"tipo_reg": 227, "nombre": "Declaració responsable d'obres"},
    {"tipo_reg": 138, "nombre": "Declaració responsable de primera ocupació"},
    {"tipo_reg": 48, "nombre": "Certificat d'informació urbanística"},
    {"tipo_reg": 237, "nombre": "Certificat de compatibilitat urbanística"},
    {"tipo_reg": 28, "nombre": "Llicència ambiental — certificat compatibilitat urbanística"},
]

RE_PAGINA = re.compile(r'href="(/va/pagina/[^"#?]+)"', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|declaraci[oó] responsable|comunicaci[oó]n previa|"
    r"primera ocupaci[oó]n|obra[s]? (?:major|menor)|autoritzaci[oó]|certificat.*urban|"
    r"cedula|c[eé]dula|informaci[oó].*urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expedient|projecte|modificaci[oó]n|reparcel|"
    r"normativa urban|sector|ue-|unidad de ejecuci|ordenan[cç]a.*urban|"
    r"inundabil|exposici[oó] p[uú]blica|compatib.*urban)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|inspector policia|convocat[oò]ria.*empleo|"
    r"modificaci[oó]n de cr[eè]dits|suplement de cr[eè]dit|presupuest|subvenci[oó]n|"
    r"empadron|festes laborals|aeat|iae|fundaci[oó] amancio|ajuda.*veh|"
    r"repartiment excedent|bases reguladores|sorteig.*jurat|menjar a casa|"
    r"major a casa|extracte acords ple|convocat[oò]ria ple|taxa prestaci[oó] transport)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|PE|PAI|RES|SECTOR|UNIDAD)[\s\-]?(?:DE[\s\-]?)?[\dA-Z./]+(?:[\s,\-yY/]+[\dA-Z./]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_GML_NS = {
    "gml": "http://www.opengis.net/gml/3.2",
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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("urban" in n or "normativa" in n):
        return "modificación normativa urbanística"
    if "informaci" in n and "public" in n:
        return "información pública"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial / sector"
    if "pgou" in n or "plan general" in n:
        return "plan general"
    if "unidad de ejecuci" in n or re.search(r"\bue-", n):
        return "unidad de ejecución"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
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
    for child in feat:
        tag = child.tag.split("}", 1)[-1]
        if tag != "msGeometry":
            continue
        for gchild in child.iter():
            gtag = gchild.tag.split("}", 1)[-1]
            if gtag == "posList" and (gchild.text or "").strip():
                return _gml_poslist_to_polygon(gchild.text.strip())
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is not None:
        pos = poly.find(".//gml:posList", _GML_NS)
        if pos is not None and (pos.text or "").strip():
            return _gml_poslist_to_polygon(pos.text.strip())
    return None


class AlgemesiAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal Digital Value (algemesi.es) + sede eAdmin tablón + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_ALL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_tramites = list(
            self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES
        )
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))
        self.ine_mun = str(self.config.get("ine_municipio") or INE_MUN)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 45, retries: int = 2, charset: str | None = None) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-algemesi/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    enc = charset or resp.headers.get_content_charset() or "utf-8"
                    return raw.decode(enc, errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.75 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*[-|].*Algemes.*$", "", t, flags=re.I).strip()
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

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, charset="iso-8859-1")
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in re.finditer(r'verAnuncio&id=([A-F0-9]+)', html, re.I):
            aid = m.group(1)
            chunk = html[m.start() : m.start() + 900]
            title_m = re.search(r"</a>\s*(?:<[^>]+>\s*)*([^<\n]{10,400})", chunk)
            title = _clean(title_m.group(1)) if title_m else ""
            if not title:
                continue
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={aid}"
            rows.append(
                {
                    "anuncio_id": aid,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(title),
                    "url": detail_url,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tram in self.licencia_tramites:
            tipo_reg = int(tram["tipo_reg"])
            nombre = str(tram.get("nombre") or f"Trámite {tipo_reg}")
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tipo_reg}"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": nombre[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": nombre[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa eAdmin; sin registro público de concesiones",
                    "tipo_reg": tipo_reg,
                    "origen": "sede_tramite",
                }
            )
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
        while start < 12000:
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
                if cod != self.ine_mun:
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
                    "url": "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz",
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
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, url.rsplit("/", 1)[-1].replace("-", " "))
            blob = f"{title} {url}"
            if RE_PROYECTO.search(blob) or any(
                k in url.lower()
                for k in ("urban", "plan", "projecte", "orden", "dvmenu/2499", "page_id=185", "page_id=1003")
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
                        "projecte",
                        "orden",
                        "normativa",
                        "informacio",
                        "pgou",
                        "sector",
                    )
                ):
                    queue.append(full)
        return rows

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
        for key in (
            "pp",
            "ue",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "anuncio_id",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _drupal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "urban" not in row.get("url", "").lower():
            return None
        return self._to_proyecto(row)

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(re.sub(r"(?i)llic[eè]ncia", "", blob)):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_licencia_tramites():
            if item["id"] not in seen:
                seen.add(item["id"])
                rows.append(item)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_tablon"}

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

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._crawl_drupal_pages():
            add(self._drupal_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_pagina"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": with_geom,
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
