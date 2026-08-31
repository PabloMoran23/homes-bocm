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

WEB_BASE = "https://www.picanya.org"
SEDE_BASE = "https://picanya.sede.dival.es"
TRANSPARENCIA_BASE = "https://transparencia.picanya.org"
MUNICIPIO = "Picanya"
ID_PREFIX = "picanya"
INE_COD_MUN = "46195"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
OFICINA_URBANISME_URL = f"{WEB_BASE}/administracio/oficina-virtual/urbanisme"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_ZON_TYPE = "Planeamiento.Zonificacion"
GVA_SUZ_TYPE = "ms:InventarioSuSuz"
GVA_ZON_OFFSETS = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000]
GVA_SUZ_OFFSETS = list(range(0, 4200, 200))

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra|UR\.\d+)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|edicto|bop|ordenanza|sector|vistabella|suz|suelo|"
    r"parcel|oeste playa|piles)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa|plaza de|agente de policia|oficial de la policia|inspector|"
    r"concurso meritos|tmag|administrativ)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ANUNCIO_ID = re.compile(r"anuncio\.aspx\?id=(\d+)", re.I)
RE_DOC_LINK = re.compile(
    r'href="((?:https://picanya\.sede\.dival\.es)?/tablondeanuncios/documento\.aspx\?id=\d+[^"]*)"',
    re.I,
)
RE_TRAMITE_URB = re.compile(
    r'href="(https://picanya\.sede\.dival\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"\s*([^<]+)",
    re.I,
)

_GML_NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "reparcel" in n:
        return "reparcelación"
    if "mod" in n and ("sector" in n or "orden" in n):
        return "modificación planeamiento"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "ordenanza" in n or "ordenança" in n:
        return "ordenanza"
    if "edicto" in n or "bop" in n:
        return "edicto / información pública"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    if "suz" in n or "suelo urbanizable" in n:
        return "suelo urbanizable"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
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


class PicanyaAyuntamientoAdapter(AyuntamientoAdapter):
    """Digital Value web (picanya.org) + sede Dival (Sedipualba) tablón RSS + ICV GVA WFS partial."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.transparencia_base = str(
            self.config.get("transparencia_base") or TRANSPARENCIA_BASE
        ).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.oficina_urbanisme_url = str(
            self.config.get("oficina_urbanisme_url") or OFICINA_URBANISME_URL
        )
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_zon_type = str(geom_cfg.get("zon_type_name") or GVA_ZON_TYPE)
        self.gva_suz_type = str(geom_cfg.get("suz_type_name") or GVA_SUZ_TYPE)
        self.gva_zon_offsets = list(geom_cfg.get("zon_offsets") or GVA_ZON_OFFSETS)
        self.gva_suz_offsets = list(geom_cfg.get("suz_offsets") or GVA_SUZ_OFFSETS)
        self.ine_cod_mun = str(self.config.get("cod_ine_mun") or INE_COD_MUN)
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-picanya/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = encoding or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-picanya/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, timeout=60, encoding="iso-8859-1")
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].strip(),
                        "%a, %d %b %Y %H:%M:%S",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "blob": title,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _collect_tramites_urb(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, timeout=60)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title in RE_TRAMITE_URB.findall(html):
            clean = _strip_html(title)
            if not re.search(r"UR\.", clean, re.I):
                continue
            rows.append(
                {
                    "titulo": clean[:500],
                    "url": href,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _enrich_anuncio_docs(self, row: dict[str, Any]) -> dict[str, Any]:
        url = row.get("url") or ""
        if "anuncio.aspx" not in url:
            return row
        try:
            html = self._fetch(url, timeout=60)
        except urllib.error.URLError:
            return row
        docs = [self._abs_sede(m.group(1)) for m in RE_DOC_LINK.finditer(html)]
        if docs:
            row = dict(row)
            row["pdf_url"] = docs[0]
            row["documentos"] = docs
        fecha = _parse_fecha_dmy(html)
        if fecha:
            row = dict(row)
            row["fecha"] = fecha
        return row

    def _parse_wfs_members(
        self, raw: bytes, *, type_name: str, label_fields: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for member in root.findall(".//wfs:member", _GML_NS):
            feat_el = member[0]
            props: dict[str, str] = {}
            geom = None
            for child in feat_el:
                tag = child.tag.split("}")[-1]
                if tag == "msGeometry":
                    pos = child.find(".//gml:posList", _GML_NS)
                    if pos is not None and pos.text:
                        geom = _gml_poslist_to_polygon(pos.text)
                else:
                    props[tag] = (child.text or "").strip()
            if props.get("cod_ine_mun") != self.ine_cod_mun or not geom:
                continue
            label = ""
            for field in label_fields:
                if props.get(field):
                    label = props[field]
                    break
            if not label:
                label = props.get("pp") or props.get("ue") or props.get("expediente") or ""
            rows.append(
                {
                    "label": label,
                    "expediente": props.get("expediente") or props.get("pp") or "",
                    "clasificacion": props.get("clasificacion") or "",
                    "geom": geom,
                    "tipo_wfs": type_name,
                }
            )
        return rows

    def _collect_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()

        for start in self.gva_zon_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "request": "GetFeature",
                    "version": "2.0.0",
                    "typeName": self.gva_zon_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.gva_wfs}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
            except urllib.error.URLError:
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            if not root.findall(".//wfs:member", _GML_NS):
                break
            batch = self._parse_wfs_members(
                raw, type_name="zonificacion", label_fields=("denominaci", "expediente")
            )
            for feat in batch:
                key = f"zon:{feat.get('expediente')}:{feat.get('label')}"
                if key not in seen:
                    seen.add(key)
                    feat["source_url"] = f"{self.gva_wfs}?startIndex={start}&typeName={self.gva_zon_type}"
                    feats.append(feat)

        for start in self.gva_suz_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": self.gva_suz_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": "200",
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.gva_wfs}?{params}"
            try:
                raw = self._fetch_bytes(url, timeout=120)
            except urllib.error.URLError:
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            if not root.findall(".//wfs:member", _GML_NS):
                break
            batch = self._parse_wfs_members(
                raw, type_name="inventario_suz", label_fields=("pp", "ue", "clasificacion")
            )
            for feat in batch:
                key = f"suz:{feat.get('label')}:{feat.get('clasificacion')}"
                if key not in seen:
                    seen.add(key)
                    feat["source_url"] = f"{self.gva_wfs}?STARTINDEX={start}&typeNames={self.gva_suz_type}"
                    feats.append(feat)

        self._gva_cache = feats
        return feats

    def _match_gva_keywords(self, title: str) -> list[str]:
        low = (title or "").lower()
        keys: list[str] = []
        for token in (
            "plan general",
            "pgou",
            "vistabella",
            "sector",
            "reparcel",
            "oeste playa",
            "piles",
            "modificaci",
            "ordenanza",
            "ordenança",
            "industrial",
            "residencial",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_gva_keywords(title)
        if not keys:
            return None

        feats = self._collect_gva_features()
        if not feats:
            return None

        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []
        for feat in feats:
            label = (feat.get("label") or "").lower()
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 1.0
            if "vistabella" in title_low and "vistabella" in label:
                score += 3.0
            if "sector" in title_low and "sector" in label:
                score += 2.0
            if "oeste playa" in title_low and "oeste playa" in label:
                score += 3.0
            if score <= 0:
                continue
            candidates.append((score, feat, feat.get("source_url") or self.gva_wfs))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        _, best_feat, source_url = candidates[0]
        geom = best_feat.get("geom")
        if not geom:
            return None

        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
            "coord_source": "portal_geometry_centroid",
        }

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica Picanya",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en picanya.sede.dival.es",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catàleg de tràmits — Àrea Urbanisme (UR.*)",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Licencias, DR y comunicaciones previas vía sede Dival",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.oficina_urbanisme_url),
                "fecha_concesion": None,
                "tipo": "oficina virtual urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Oficina virtual — Urbanisme",
                "url": self.oficina_urbanisme_url,
                "source": "ayuntamiento",
                "nota": "Trámites UR.* enlazados desde web municipal Digital Value",
                "origen": "web_tramite",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("url") or blob
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None

        key = row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "tablon",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _collect_planeamiento_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        feats = self._collect_gva_features()
        labels: set[str] = set()
        for feat in feats:
            label = (feat.get("label") or "").strip()
            if not label or label in labels:
                continue
            labels.add(label)
            exp = feat.get("expediente") or ""
            clas = feat.get("clasificacion") or ""
            titulo = f"{label} ({clas})" if clas and clas not in label else label
            if exp and exp not in titulo:
                titulo = f"{titulo} (exp. {exp})"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"gva:{exp}:{label}:{clas}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(label),
                "url": feat.get("source_url") or self.gva_wfs,
                "source": "ayuntamiento",
                "origen": "gva_wfs",
                "expte": exp or None,
            }
            geom = feat.get("geom")
            if geom:
                rec.update(
                    {
                        "geom_geojson": geom,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": feat.get("source_url") or self.gva_wfs,
                        "coord_source": "portal_geometry_centroid",
                    }
                )
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_tramite_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tramites_urb():
            rec: dict[str, Any] = {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": None,
                "tipo": "trámite urbanismo",
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            }
            rows.append(rec)
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon_rss():
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

        for item in self._collect_tablon_rss():
            enriched = self._enrich_anuncio_docs(item)
            add(self._tablon_to_proyecto(enriched))

        for seed in self._collect_planeamiento_seeds():
            add(seed)

        for tramite in self._collect_tramite_proyectos():
            add(tramite)

        add(
            {
                "id": _stable_id("proy", self.transparencia_base),
                "municipio": MUNICIPIO,
                "titulo": "Portal de transparència municipal",
                "fecha": None,
                "tipo": "transparencia",
                "url": self.transparencia_base,
                "source": "ayuntamiento",
                "origen": "transparencia",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
            "gva_wfs": sum(1 for r in rows if r.get("origen") == "gva_wfs"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
