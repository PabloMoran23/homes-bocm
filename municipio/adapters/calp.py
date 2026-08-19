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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.calp.es"
SEDE_BASE = "https://calp.sedelectronica.es"
MUNICIPIO = "Calp"
ID_PREFIX = "calp"
INE_COD_MUN = "03047"

TRANSPARENCY_PLANEAMIENTO = (
    f"{SEDE_BASE}/transparency/a24a7907-f637-483f-9b3c-a736b5027b3e/"
)
GEOPORTAL_URL = "https://geoportal.calp.es/"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "Planeamiento.Zonificacion"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra|suspensi[oó]n de licencias)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|convenio|edicto|dogv|bop|d-\d+|sector|suelo|"
    r"ba[nñ]os de la reina|morello|la fossa|saladar|documentaci[oó]n t[eé]cnica)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"contrataciones|concesi[oó]n de subvenciones|bono consumo|taxi|"
    r"auxiliar t[eé]cnico|empleo p[uú]blico)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://calp\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_MOD_CODE = re.compile(r"(?i)\bD-\d+\b")


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
    n = title.lower()
    if "plan especial" in n or "baños de la reina" in n or "banos de la reina" in n:
        return "plan especial"
    if re.search(r"\bd-\d+", n):
        return "modificación puntual PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n or "dogv" in n:
        return "información pública"
    if "convenio" in n:
        return "convenio urbanístico"
    if "documentaci" in n and "t" in n and "cnica" in n:
        return "documentación técnica"
    if "licencia" in n:
        return "licencia publicada"
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


class CalpAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal calp.es transparencia + tablón espublico + ICV GVA WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_planeamiento_url") or TRANSPARENCY_PLANEAMIENTO
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-calp/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_transparency(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSPARENCY_ROW.finditer(html):
            row_html = m.group(0)
            if "preview-document" not in row_html:
                continue
            preview_m = RE_PREVIEW_LINK.search(row_html)
            if not preview_m:
                continue
            url = preview_m.group(1)
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            titulo = _strip_html(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            if title_m and len(title_m.group(1).strip()) > 10:
                titulo = title_m.group(1).strip()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "origen": "sede_transparencia",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", GEOPORTAL_URL),
                "fecha_concesion": None,
                "tipo": "visor cartográfico municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Geoportal municipal — consulta PGOU",
                "url": GEOPORTAL_URL,
                "source": "ayuntamiento",
                "nota": "Visor Geonet; sin API REST enlazada a expedientes",
                "origen": "geoportal_info",
            },
        ]

    def _load_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": GVA_WFS_TYPE,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "5000",
            }
        )
        url = f"{GVA_WFS}?{params}"
        feats: list[dict[str, Any]] = []
        try:
            raw = self._fetch(url, timeout=120)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            self._gva_cache = feats
            return feats
        ns = {
            "wfs": "http://www.opengis.net/wfs/2.0",
            "gml": "http://www.opengis.net/gml",
        }
        for member in root.findall(".//wfs:member", ns):
            feat_el = member[0]
            props: dict[str, str] = {}
            geom = None
            for child in feat_el:
                tag = child.tag.split("}")[-1]
                if tag == "msGeometry":
                    pos = child.find(".//gml:posList", ns)
                    if pos is not None and pos.text:
                        geom = _gml_poslist_to_polygon(pos.text)
                else:
                    props[tag] = (child.text or "").strip()
            if props.get("cod_ine_mun") != INE_COD_MUN:
                continue
            if not geom:
                continue
            label = props.get("denominaci") or props.get("expediente") or ""
            feats.append(
                {
                    "label": label,
                    "zon_suelo": props.get("zon_suelo") or "",
                    "descripcio": props.get("descripcio") or "",
                    "info_adici": props.get("info_adici") or "",
                    "expediente": props.get("expediente") or "",
                    "geom": geom,
                    "source_url": (
                        f"{GVA_WFS}?service=WFS&request=GetFeature&"
                        f"CQL_FILTER=cod_ine_mun%3D%27{INE_COD_MUN}%27"
                    ),
                }
            )
        self._gva_cache = feats
        return feats

    def _match_keywords(self, title: str) -> list[str]:
        low = title.lower()
        keys: list[str] = []
        for m in RE_MOD_CODE.finditer(title):
            keys.append(m.group(0).lower())
        for token in (
            "baños de la reina",
            "banos de la reina",
            "morello",
            "la fossa",
            "saladar",
            "pgou",
            "plan general",
            "plan especial",
            "modificaci",
            "convenio",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_keywords(title)
        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []

        for item in self._load_gva_features():
            label = item["label"].lower()
            info = item.get("info_adici", "").lower()
            desc = item.get("descripcio", "").lower()
            blob = f"{label} {info} {desc} {item.get('zon_suelo', '').lower()}"
            score = 0.0
            for k in keys:
                if k in blob or k in title_low:
                    score += 20
            if "pgou" in title_low and "plan general" in label:
                score += 25
            if "baños de la reina" in title_low or "banos de la reina" in title_low:
                if "plan general" in label:
                    score += 15
            if "morello" in title_low or "fossa" in title_low or "saladar" in title_low:
                if "plan general" in label:
                    score += 10
            if score >= 15:
                candidates.append((score, item["geom"], item["source_url"]))

        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        top_score = candidates[0][0]
        geoms = [g for s, g, _ in candidates if s >= top_score - 5]
        merged = _merge_geometries(geoms)
        if not merged:
            return None
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": candidates[0][2],
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

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "legalidad")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row.get("blob") or row.get("titulo") or ""):
            return None
        key = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_transparencia",
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif "legalidad" in proc:
            tipo = "protección legalidad urbanística"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "sede_board",
        }
        self._enrich_geometry(rec)
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "geoportal_info")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_transparency():
            add(self._transparency_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if r.get("origen") == "sede_transparencia"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
