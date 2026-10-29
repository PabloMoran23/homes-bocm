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

WEB_BASE = "https://petrer.es"
SEDE_BASE = "https://sede.petrer.es"
MUNICIPIO = "Petrer"
ID_PREFIX = "petrer"
INE_COD_MUN = "03104"
WP_CAT_URBANISMO = 188

CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
URBANISMO_URL = f"{WEB_BASE}/concejalia-de-urbanismo/"
GEOPETRER_URL = (
    "http://petrer.maps.arcgis.com/apps/webappviewer/index.html?id=ae0068931a864a2c83f916b9f7295fa5"
)

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_ZON = "Planeamiento.Zonificacion"
GVA_ZON_OFFSETS = [2000]

WP_SEARCH_TERMS = (
    "información pública",
    "exposición pública",
    "modificación puntual",
    "plan parcial",
    "estudio de integración",
)

RE_H2 = re.compile(
    r'class="elementor-heading-title[^"]*"[^>]*>([^<]+)</h2>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|compatibilidad urban|informe de compatibilidad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|sector|uzi|luvi|polideportivo|integraci[oó]n paisag|ordenanza.*edificaci|"
    r"programa de actuaci|plan estrat[eé]gico|reurbanizaci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|convocatoria de ayudas|empleo|tasa de basura|"
    r"iluminaci[oó]n esc[eé]nica|sala de estudio|escuela infantil|comercio|"
    r"comunidad energ[eé]tica|valor de tasaci[oó]n|edificant|plan barrio)",
)
RE_PDF = re.compile(r'https://petrer\.es/wp-content/uploads/[^"\s]+\.pdf', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan parcial" in n or "sector" in n or "uzi" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "integraci" in n and "paisag" in n:
        return "estudio de integración"
    if "polideportivo" in n:
        return "equipamiento"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "programa de actuaci" in n:
        return "programa de actuación"
    if "plan general" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.strip().split()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class PetrerAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress petrer.es + sede STA (catálogo) + ICV WFS Zonificacion + GeoPetrer (referencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS)
        self.gva_zon_type = str(geom_cfg.get("zon_type_name") or GVA_WFS_ZON)
        self.gva_zon_offsets = list(geom_cfg.get("zon_offsets") or GVA_ZON_OFFSETS)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_COD_MUN)
        self.mun_name = str(geom_cfg.get("mun_name") or MUNICIPIO)
        self._zon_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-petrer/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 120) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-petrer/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen_ids: set[int] = set()
        rows: list[dict[str, Any]] = []
        queries: list[dict[str, str]] = [
            {"categories": str(WP_CAT_URBANISMO)},
        ]
        for term in WP_SEARCH_TERMS:
            queries.append({"search": term})

        for params in queries:
            q = {
                "per_page": "100",
                "_fields": "id,link,title,date,content",
                **params,
            }
            url = f"{self.web_base}/wp-json/wp/v2/posts?{urllib.parse.urlencode(q)}"
            try:
                raw = self._fetch(url, timeout=60)
                posts = json.loads(raw)
            except (urllib.error.URLError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                pid = post.get("id")
                if not isinstance(pid, int) or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                title = _clean_title(str((post.get("title") or {}).get("rendered") or ""))
                if not title:
                    continue
                content = str((post.get("content") or {}).get("rendered") or "")
                pdfs = RE_PDF.findall(content)
                rows.append(
                    {
                        "titulo": title,
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or self.urbanismo_url,
                        "pdf_urls": pdfs,
                        "origen": "wp_rest",
                    }
                )
        return rows

    def _collect_urbanismo_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url, timeout=60)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for heading in RE_H2.findall(html):
            titulo = _clean_title(heading)
            if not RE_LICENCIA.search(titulo):
                continue
            if titulo.lower().startswith("anuncios") or titulo.lower().startswith("noticias"):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": None,
                    "url": self.urbanismo_url,
                    "origen": "web_tramite_info",
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, timeout=60)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "url": self._tramite_url(dboid),
                    "origen": "sede_catalogo",
                }
            )
        return rows

    def _parse_wfs_member(self, feat_el: ET.Element) -> dict[str, Any] | None:
        props: dict[str, str] = {}
        geom = None
        for child in feat_el:
            tag = child.tag.split("}")[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}")[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if props.get("noms_mun", "").lower() != self.mun_name.lower():
            return None
        label = props.get("denominaci") or props.get("pp") or props.get("clasificacion") or ""
        if not label:
            return None
        return {
            "label": label,
            "expediente": props.get("expediente") or props.get("id") or "",
            "clasificacion": props.get("clasificacion") or "",
            "fecha": props.get("f_aprob") or props.get("f_public"),
            "geom": geom,
            "url_abs": props.get("url_abs") or "",
        }

    def _collect_zon_features(self) -> list[dict[str, Any]]:
        if self._zon_cache is not None:
            return self._zon_cache

        feats: list[dict[str, Any]] = []
        seen: set[str] = set()
        ns = {"wfs": "http://www.opengis.net/wfs/2.0"}

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
                raw = self._fetch_bytes(url, timeout=180)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                continue

            for member in root.findall(".//wfs:member", ns):
                parsed = self._parse_wfs_member(member[0])
                if not parsed:
                    continue
                key = f"{parsed.get('expediente')}:{parsed.get('label')}"
                if key in seen:
                    continue
                seen.add(key)
                parsed["source_url"] = url
                feats.append(parsed)

        self._zon_cache = feats
        return feats

    def _match_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = (titulo or "").lower()
        if not title:
            return None
        keys = []
        for token in (
            "plan general",
            "pgou",
            "modificaci",
            "sector",
            "uzi",
            "luvi",
            "polideportivo",
            "integraci",
            "programa de actuaci",
        ):
            if token in title:
                keys.append(token)
        best: dict[str, Any] | None = None
        best_score = 0
        for feat in self._collect_zon_features():
            label = str(feat.get("label") or "").lower()
            if not feat.get("geom"):
                continue
            score = sum(1 for k in keys if k in label or k in title)
            if "plan general" in title and "plan general" in label:
                score += 3
            if score > best_score:
                best_score = score
                best = feat
        if not best or not best.get("geom") or best_score <= 0:
            return None
        geom = best["geom"]
        return {
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_wfs",
            "geometry_source_url": best.get("source_url"),
            "coord_source": "portal_geometry_centroid",
            "lat": None,
            "lon": None,
        }

    def _apply_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geo = self._match_geometry(str(rec.get("titulo") or ""))
        if not geo:
            return
        rec.update(geo)
        centroid = geometry_centroid(geo["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = titulo
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(
            r"(?i)modificaci|plan parcial|informaci|exposici|programa de actuaci|ordenanza",
            blob,
        ):
            return None
        pdf = row.get("pdf_urls")[0] if row.get("pdf_urls") else None
        key = pdf or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha") or _fecha_from_blob(titulo),
            "tipo": _proyecto_tipo(blob),
            "url": pdf or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
        return rec

    def _wfs_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        titulo = _clean_title(str(feat.get("label") or "Instrumento planeamiento"))
        key = f"wfs:{feat.get('expediente')}:{titulo}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _parse_fecha_dmy(str(feat.get("fecha") or "")) or None,
            "tipo": _proyecto_tipo(titulo),
            "url": feat.get("url_abs") or GEOPETRER_URL,
            "source": "ayuntamiento",
            "origen": "icv_wfs_zonificacion",
            "expediente": feat.get("expediente"),
            "clasificacion": feat.get("clasificacion"),
        }
        geom = feat.get("geom")
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = feat.get("source_url")
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"] + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite informativo; sin listado público de concesiones",
            "origen": row.get("origen"),
        }

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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._collect_urbanismo_tramites() + self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_wp_posts():
            add(self._wp_to_proyecto(row))
        for feat in self._collect_zon_features():
            add(self._wfs_to_proyecto(feat))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_web_sede"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wp_rest_icv_wfs"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
