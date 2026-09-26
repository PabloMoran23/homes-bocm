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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.lavallduixo.es"
SEDE_BASE = "https://sede.lavallduixo.es"
MUNICIPIO = "La Vall d'Uixó"
ID_PREFIX = "la-vall-d-uixo"
COD_INE_MUN = "12125"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&lang=ES"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"

ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE_NAME = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(0, 14000, 500))

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/planeamiento-urbanistico",
    f"{WEB_BASE}/es/plan-general-de-ordenacion-urbana",
    f"{WEB_BASE}/es/exposicion-al-publico",
    f"{WEB_BASE}/es/plan-especial-de-san-jose",
    f"{WEB_BASE}/es/plan-parcial-sector-1-c",
    f"{WEB_BASE}/es/plan-parcial-sector-2-carmaday",
    f"{WEB_BASE}/es/plan-parcial-sector-4-belcaire",
    f"{WEB_BASE}/es/plan-parcial-sector-12",
    f"{WEB_BASE}/es/plan-parcial-area-6",
    f"{WEB_BASE}/es/plan-parcial-area-7",
    f"{WEB_BASE}/es/plan-parcial-area-8",
    f"{WEB_BASE}/es/plan-parcial-area-9a",
    f"{WEB_BASE}/es/plan-parcial-area-10",
    f"{WEB_BASE}/es/plan-parcial-area-11",
    f"{WEB_BASE}/es/plan-parcial-reclasificacion-sumet",
    f"{WEB_BASE}/es/plan-parcial-reclasificacion-la-mezquita",
    f"{WEB_BASE}/es/pmus",
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia urbanística",
    "licencia de obra",
    "licencia de división horizontal",
    "declaración responsable de primera ocupación",
    "certificado urbanístico",
    "comunicación previa",
    "declaración responsable ambiental",
)

PROYECTO_TRAMITE_PATTERNS: tuple[str, ...] = (
    "convenios urbanísticos",
    "programas de actuación urbanística",
    "certificados de disciplina urbanística",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|solicitud de licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pmus|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|sector|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|normas subsidiarias|exposici[oó]n|"
    r"reclasificaci[oó]n|san jos[eé]|belcaire|carmaday|sumet|mezquita)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|impuesto sobre actividades|iae|cobranza|"
    r"padrones|subvenci[oó]n deportiv|bolsa de oficial)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:files|uploads)/(\d{4})-(\d{2})/")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_SECTOR = re.compile(r"(?i)sector\s*([0-9IVXLC]+(?:\s*[-/]\s*[A-Z0-9]+)?)")
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pmus" in n or "movilidad urbana" in n:
        return "PMUS"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "exposici" in n or "informaci" in n:
        return "información pública"
    if "pgou" in n or "normas subsidiarias" in n or "plan general" in n:
        return "PGOU"
    if "reclasificaci" in n:
        return "reclasificación"
    return "planeamiento"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        g = feat.get("geometry")
        if not isinstance(g, dict):
            continue
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


class LaVallDUixoAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 9 (TOOOLS) + sede STA tablón/catálogo + ICV WFS Zonificacion (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS_BASE).rstrip("/")
        self.icv_type_name = str(geom_cfg.get("type_name") or ICV_TYPE_NAME)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._icv_zones_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False, timeout: float = 90) -> str:
        time.sleep(self.delay_s)
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-vall-d-uixo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, timeout: float = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-vall-d-uixo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _extract_tablon_dataset(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_PTS2_TABLON = "
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

    @staticmethod
    def _extract_catalog_items(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_CATSERV = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        items: list[dict[str, Any]] = []
        for row in data if isinstance(data, list) else []:
            dboid = str(row.get("dboid") or "")
            name = _clean_title(str(row.get("name") or ""))
            if name and dboid:
                items.append({"titulo": name, "dboid": dboid, "origen": "catalogo_tramites"})
        return items

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True, timeout=120)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_tablon_dataset(html):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True, timeout=120)
        except urllib.error.URLError:
            return []
        return [
            {**item, "url": self._tramite_url(item["dboid"])}
            for item in self._extract_catalog_items(html)
        ]

    def _collect_drupal_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=45)
            except urllib.error.URLError:
                continue
            h1_m = RE_H1.search(html)
            page_title = _clean_title(h1_m.group(1)) if h1_m else page_url.rsplit("/", 1)[-1]

            page_key = f"page:{page_url}"
            if page_key not in seen:
                seen.add(page_key)
                rows.append(
                    {
                        "titulo": page_title,
                        "fecha": _fecha_from_url(page_url),
                        "url": page_url,
                        "origen": "drupal_page",
                        "blob": page_title,
                    }
                )

            for m in RE_PDF.finditer(html):
                href = m.group(1)
                doc_url = urljoin(page_url, href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                name = unescape(unquote(Path(href).name))
                rows.append(
                    {
                        "titulo": f"{page_title} — {name}",
                        "fecha": _fecha_from_url(doc_url) or _fecha_from_url(page_url),
                        "url": doc_url,
                        "page_url": page_url,
                        "origen": "drupal_pdf",
                        "blob": f"{page_title} {name}",
                    }
                )
        return rows

    def _collect_icv_zones(self) -> list[dict[str, Any]]:
        if self._icv_zones_cache is not None:
            return self._icv_zones_cache

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for start in self.icv_offsets:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.icv_type_name,
                    "outputFormat": "application/json; subtype=geojson",
                    "srsName": "EPSG:4326",
                    "count": "500",
                    "startIndex": str(start),
                }
            )
            url = f"{self.icv_wfs_url}?{params}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            batch = data.get("features") or []
            if not batch:
                break
            for feat in batch:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
                    continue
                den = str(props.get("denominaci") or "").strip()
                exp = str(props.get("expediente") or "").strip()
                if den:
                    grouped.setdefault((den, exp), []).append(feat)

        zones: list[dict[str, Any]] = []
        for (den, exp), feats in grouped.items():
            zones.append(
                {
                    "denominaci": den,
                    "expediente": exp,
                    "tipo": _proyecto_tipo(den),
                    "geom_geojson": _merge_geometries(feats),
                    "geometry_source_url": (
                        f"{self.icv_wfs_url}?service=WFS&request=GetFeature&"
                        f"typeName={self.icv_type_name}&cod_ine_mun={self.cod_ine_mun}"
                    ),
                }
            )
        self._icv_zones_cache = zones
        return zones

    def _match_icv_zone(self, titulo: str) -> dict[str, Any] | None:
        norm = re.sub(r"\s+", " ", (titulo or "").upper())
        sector_m = RE_SECTOR.search(titulo or "")
        sector = sector_m.group(1).upper().replace(" ", "") if sector_m else None
        best: tuple[float, dict[str, Any]] | None = None

        for zone in self._collect_icv_zones():
            den = re.sub(r"\s+", " ", (zone.get("denominaci") or "").upper())
            score = 0.0
            if den and den in norm:
                score = 100.0
            elif sector and f"SECTOR {sector}" in den:
                score = 80.0
            elif "NORMAS SUBSIDIARIAS" in norm and "NORMAS SUBSIDIARIAS" in den:
                score = 90.0
            elif "PGOU" in norm and "PLAN GENERAL" in den:
                score = 70.0
            else:
                tokens = [t for t in re.split(r"[^A-Z0-9]+", den) if len(t) >= 5]
                hits = sum(1 for t in tokens if t in norm)
                score = hits * 10.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, zone)

        if best and best[0] >= 20:
            return best[1]
        return None

    def _zone_geometry(self, zone: dict[str, Any]) -> dict[str, Any] | None:
        geom = zone.get("geom_geojson")
        if not geom:
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": zone.get("geometry_source_url") or self.icv_wfs_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        zone = self._match_icv_zone(rec.get("titulo") or "")
        if not zone:
            return
        geom = self._zone_geometry(zone)
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_icv_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visor = "https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion"
        for zone in self._collect_icv_zones():
            titulo = zone["denominaci"]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"icv:{zone['expediente']}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": zone.get("tipo") or "planeamiento",
                "url": visor,
                "source": "ayuntamiento",
                "origen": "icv_wfs",
                "expte": zone.get("expediente"),
            }
            geom = self._zone_geometry(zone)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(geom["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia", blob):
            return None
        key = row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if m := RE_EXPTE.search(row["titulo"]):
            rec["expte"] = m.group(1)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        low = titulo.lower()
        if not any(p in low for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('blob', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("dboid") or row.get("url")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if m := RE_EXPTE.search(titulo):
            rec["expte"] = m.group(1)
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

        info = {
            "id": _stable_id("lic", TABLON_URL),
            "fecha_concesion": None,
            "tipo": "tablón licencias urbanísticas",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": "Tablón de anuncios — sede electrónica",
            "url": TABLON_URL,
            "source": "ayuntamiento",
            "nota": "Edictos y anuncios en sede STA; sin histórico de concesiones",
            "origen": "sede_tablon",
        }
        rows.append(info)
        seen.add(info["id"])

        for item in self._tablon_rows():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._catalog_rows():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_icv_proyectos():
            add(rec)
        for item in self._collect_drupal_docs():
            add(self._row_to_proyecto(item))
        for item in self._tablon_rows():
            add(self._row_to_proyecto(item))
        for item in self._catalog_rows():
            titulo = item["titulo"]
            if any(p in titulo.lower() for p in PROYECTO_TRAMITE_PATTERNS) or RE_PROYECTO.search(titulo):
                add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal_")),
            "icv": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
