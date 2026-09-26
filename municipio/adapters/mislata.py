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

BASE = "https://www.mislata.es"
SEDE = "https://mislata.sedipualba.es"
MUNICIPIO = "Mislata"
ID_PREFIX = "mislata"
INE_MUN = "46169"

TABLON_RSS = f"{SEDE}/tablondeanuncios/tablon_rss.aspx"
CATALOGO_TRAMITES = f"{SEDE}/catalogoservicios.aspx"
ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"
VISOR_GVA = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos",
    f"{BASE}/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/plan-general-de-ordenacion-urbana",
    f"{BASE}/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/planes-urbanisticos-en-tramite",
    f"{BASE}/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/plano-de-clasificacion-del-suelo",
    f"{BASE}/es/administracion/oficina-virtual/urbanismo",
]

RE_PLANEAM_PATH = re.compile(
    r'href="(/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos[^"#?]+)"',
    re.I,
)
RE_TRAMITE = re.compile(
    r'href="(https://mislata\.sedipualba\.es/(?:carpetaciudadana|segex)/tramite\.aspx\?idtramite=\d+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|informe urban|obra[s]? (?:major|menor)|"
    r"demolici[oó]n|edificaci[oó]n|ocupaci[oó]n de v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|ue-|sd-|suz|normativa urban|plantejament|"
    r"homologaci[oó]n|edicto|clasificaci[oó]n del suelo|integraci[oó]n paisaj|"
    r"quint|villarrasa|vinyes|paquillo)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|empleo p[uú]blico|polic[ií]a local|bolsa de|"
    r"cementerio|exhumaci[oó]n|valenciano|psicot[eé]cnico)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|SEQUIAR|QUINT|VILLARRASA|VINYES|PAQUILLO)[\s\-]?(?:IND\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
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
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or "sector" in n or "homologaci" in n:
        return "plan parcial"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "edicto" in n:
        return "edicto urbanístico"
    if "clasificaci" in n and "suelo" in n:
        return "clasificación del suelo"
    if "integraci" in n and "paisaj" in n:
        return "estudio integración paisajística"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
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


class MislataAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portales (mislata.es) + sede sedipualba + ICV WFS (partial geometry)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 40))
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("layer_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("layer_zon") or ICV_LAYER_ZON)
        self.cod_ine_mun = str(geom_cfg.get("ine_municipio") or INE_MUN)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mislata/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                for enc in ("utf-8", "latin-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

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
                t = re.sub(r"\s*[-|].*Mislata.*$", "", t, flags=re.I).strip()
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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source_url in (CATALOGO_TRAMITES, f"{BASE}/es/administracion/oficina-virtual/urbanismo"):
            try:
                html = self._fetch(source_url)
            except urllib.error.URLError:
                continue
            for href, title in RE_TRAMITE.findall(html):
                titulo = _clean(unescape(title))
                if href in seen:
                    continue
                seen.add(href)
                rows.append({"titulo": titulo, "url": href, "origen": "sede_tramite"})
        return rows

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(TABLON_RSS)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw.encode("latin-1", errors="replace"))
        except ET.ParseError:
            return []
        for item in root.findall(".//item"):
            title = _clean(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "origen": "tablon_rss"})
        return rows

    def _crawl_transparencia_pages(self) -> list[dict[str, Any]]:
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
            if RE_PROYECTO.search(blob) or "planeamientos-urbanisticos" in url:
                rows.append(
                    {
                        "titulo": title,
                        "url": url,
                        "fecha": _parse_fecha_dmy(html) or _parse_fecha_dmy(title),
                        "origen": "drupal_transparencia",
                    }
                )
            for href in RE_PDF.findall(html):
                pdf_url = self._abs_web(href)
                pdf_title = f"{title} — PDF"
                rows.append(
                    {
                        "titulo": pdf_title[:500],
                        "url": pdf_url,
                        "fecha": _parse_fecha_dmy(pdf_url) or _parse_fecha_dmy(title),
                        "origen": "drupal_pdf",
                        "parent_title": title,
                    }
                )
            for href in RE_PLANEAM_PATH.findall(html):
                full = self._abs_web(href).rstrip("/")
                if full not in seen_pages and full not in queue:
                    queue.append(full)
        return rows

    def _wfs_page_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": type_name,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _parse_wfs_member(self, member: ET.Element, *, layer: str) -> dict[str, Any] | None:
        feat = None
        for tag in (f"{{{_GML_NS['ms']}}}{layer}", f"{{{_GML_NS['ms']}}}InventarioSuSuz"):
            feat = member.find(tag)
            if feat is not None:
                break
        if feat is None:
            for child in member:
                if child.tag.endswith("InventarioSuSuz") or child.tag.endswith("Zonificacion"):
                    feat = child
                    break
        if feat is None:
            return None
        cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
        if cod != self.cod_ine_mun:
            return None
        fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
        pp = _clean(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
        ue = _clean(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
        denom = _clean(
            feat.findtext("ms:denominaci", default="", namespaces=_GML_NS)
            or feat.findtext("ms:denominaci_val", default="", namespaces=_GML_NS)
            or ""
        )
        clas = _clean(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
        exp = _clean(feat.findtext("ms:expediente", default="", namespaces=_GML_NS) or "")
        f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
        titulo = pp or denom or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"
        geom = _gml_feature_to_geojson(feat)
        url_abs = feat.findtext("ms:url_abs", default="", namespaces=_GML_NS) or VISOR_GVA
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": f_aprob or _parse_fecha_dmy(exp),
            "url": url_abs,
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "clasificacion": clas or None,
            "pp": pp or None,
            "ue": ue or None,
            "expediente": exp or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._wfs_page_url(self.icv_layer_su, 0)
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "InventarioSuSuz"), (self.icv_layer_zon, "Zonificacion")):
            start = 0
            while start < 12000:
                url = self._wfs_page_url(type_name, start)
                try:
                    raw = self._fetch(url, timeout=90)
                    root = ET.fromstring(raw)
                except (urllib.error.URLError, ET.ParseError):
                    break
                members = root.findall(".//wfs:member", _GML_NS)
                if not members:
                    break
                for member in members:
                    rec = self._parse_wfs_member(member, layer=layer.split(".")[-1])
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                start += 200
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (
                rec.get("titulo") or "",
                rec.get("pp") or "",
                rec.get("ue") or "",
                rec.get("expediente") or "",
            ):
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
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "parent_title", "pp", "ue", "expediente"))
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
        for key in (
            "pp",
            "ue",
            "expediente",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "parent_title",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _drupal_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "planeamientos-urbanisticos" not in row.get("url", ""):
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        rows.append(
            {
                "id": _stable_id("lic", TABLON_RSS),
                "fecha_concesion": None,
                "tipo": "tablón sedipualba",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Mislata",
                "url": TABLON_RSS,
                "source": "ayuntamiento",
                "nota": "RSS tablón; sin licencias urbanísticas recientes en feed",
                "origen": "sede_tablon",
            }
        )
        for item in self._collect_tablon_rss():
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
        for item in self._crawl_transparencia_pages():
            add(self._drupal_to_proyecto(item))
        for item in self._collect_tablon_rss():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
