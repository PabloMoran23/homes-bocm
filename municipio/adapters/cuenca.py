from __future__ import annotations

import hashlib
import json
import re
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

GMU_BASE = "https://gerenciaurbanismo.cuenca.es"
AYTO_IMPRESOS = "https://ayuntamiento.cuenca.es/impresos-y-formularios"
MUNICIPIO = "Cuenca"
ID_PREFIX = "cuenca"
INE_MUN = "16078"

CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{GMU_BASE}/plan-general",
    f"{GMU_BASE}/planes-especiales",
    f"{GMU_BASE}/plan-general-provisional",
    f"{GMU_BASE}/desarrollo-urbano-sostenible",
    f"{GMU_BASE}/ordenanzas-municipales",
    f"{GMU_BASE}/catalogo-bic",
    f"{GMU_BASE}/requisitos",
    f"{GMU_BASE}/tablon-anuncios",
]

RE_PDF_OR_ZIP = re.compile(
    r'href=["\']([^"\']+\.(?:pdf|zip)(?:\?[^"\']*)?)["\']',
    re.I,
)
RE_FILE_DOWNLOAD = re.compile(
    r'href=["\']([^"\']*fileDownload\.aspx[^"\']+)["\']',
    re.I,
)
RE_IMPRESO_PDF = re.compile(
    r'href=["\']([^"\']+/Portals/Ayuntamiento/documents/[^"\']+\.pdf)["\']',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n (?:previa|urban)|obra[s]? (?:mayor|menor)|primera ocupaci[oó]n|"
    r"ocupaci[oó]n de v[ií]a p[uú]blica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"calificaci[oó]n|normas urban|ordenaci[oó]n|memoria|planos|bic|"
    r"desarrollo urbano|ordenanza)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(y.group(1))
        for y in RE_YEAR.finditer(text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan especial" in n or "planes especiales" in n:
        return "plan especial"
    if "calificaci" in n:
        return "calificación del suelo"
    if "ordenaci" in n and "detall" in n:
        return "ordenación detallada"
    if "bic" in n or "bienes" in n:
        return "catálogo BIC"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "desarrollo urbano" in n:
        return "desarrollo urbano sostenible"
    return "urbanismo"


class CuencaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal DNN Gerencia Urbanismo (cuenca.es) + impresos ayuntamiento + ArcGIS CLM PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or GMU_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.gmu_base = str(self.config.get("gmu_base") or GMU_BASE).rstrip("/")
        self.ayto_impresos = str(self.config.get("ayto_impresos") or AYTO_IMPRESOS)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or INE_MUN)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cuenca/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cuenca/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_gmu(self, href: str) -> str:
        href = unescape(href.strip())
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        return urllib.parse.urljoin(f"{self.gmu_base}/", href.lstrip("/"))

    def _abs_ayto(self, href: str) -> str:
        href = unescape(href.strip())
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin("https://ayuntamiento.cuenca.es/", href.lstrip("/"))

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

    def _extract_docs_from_html(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pattern in (RE_PDF_OR_ZIP, RE_FILE_DOWNLOAD, RE_IMPRESO_PDF):
            for m in pattern.finditer(html):
                url = self._abs_gmu(m.group(1))
                if "ayuntamiento.cuenca.es" in m.group(1) or "/Portals/Ayuntamiento/" in m.group(1):
                    url = self._abs_ayto(m.group(1))
                if url in seen:
                    continue
                seen.add(url)
                fname = urllib.parse.unquote(url.rsplit("/", 1)[-1].split("?")[0])
                titulo = _clean(fname.replace("_", " ").replace("+", " "))
                rows.append(
                    {
                        "titulo": titulo[:500] or url,
                        "url": url,
                        "fecha": _parse_fecha(fname) or _parse_fecha(titulo),
                        "origen": "gmu_documento",
                        "page": page_url,
                    }
                )
        return rows

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
        nom = str(meta.get("nom_plan") or "Plan General de Ordenación Urbana")
        url = str(meta.get("descarga") or f"{self.gmu_base}/plan-general")
        return {
            "titulo": f"{nom} — {MUNICIPIO} (CLM)",
            "fecha": None,
            "url": url,
            "tipo": "PGOU",
            "origen": "clm_arcgis",
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": meta.get("geometry_source_url"),
            "coord_source": "portal_geometry_centroid",
        }

    def _attach_pgou_if_plan(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = (rec.get("titulo") or "").lower()
        if "pgou" not in blob and "plan general" not in blob and "calificaci" not in blob:
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

    def _crawl_gmu_seeds(self) -> list[dict[str, Any]]:
        page_rows: list[dict[str, Any]] = []
        doc_rows: list[dict[str, Any]] = []
        for url in self.seed_pages:
            try:
                html = self._fetch(url, timeout=45)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
            section = _clean(title_m.group(1)) if title_m else url.rsplit("/", 1)[-1]
            page_rows.append(
                {
                    "titulo": f"{section} — Gerencia Urbanismo Cuenca",
                    "url": url,
                    "fecha": _parse_fecha(html),
                    "origen": "gmu_seccion",
                    "tipo": _proyecto_tipo(section),
                }
            )
            for doc in self._extract_docs_from_html(html, url):
                doc["tipo"] = _proyecto_tipo(doc["titulo"])
                doc_rows.append(doc)
        return page_rows + doc_rows

    def _collect_requisitos_licencias(self) -> list[dict[str, Any]]:
        url = f"{self.gmu_base}/requisitos"
        try:
            html = self._fetch(url, timeout=45)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>.*?'
            r"(?:fa-cloud-download|Descargar)[^<]*</a>\s*&nbsp;([^<]+)",
            html,
            re.I | re.S,
        ):
            href, title = m.group(1), _clean(m.group(2))
            if not RE_LICENCIA.search(title):
                continue
            doc_url = self._abs_gmu(href)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            rows.append({"titulo": title[:500], "url": doc_url, "origen": "gmu_requisitos"})
        for m in re.finditer(
            r'aria-controls="#cp\d+"[^>]*><em[^>]*></em>([^<]+)</a>',
            html,
            re.I,
        ):
            title = _clean(m.group(1))
            if not RE_LICENCIA.search(title):
                continue
            key = f"req:{title}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "origen": "gmu_requisitos",
                    "nota": "Instrucciones/requisitos; ver PDF en la misma página",
                }
            )
        return rows

    def _collect_impresos_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ayto_impresos, timeout=45)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_IMPRESO_PDF.finditer(html):
            href = m.group(1)
            if not RE_LICENCIA.search(href):
                continue
            doc_url = self._abs_ayto(href)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            fname = urllib.parse.unquote(doc_url.rsplit("/", 1)[-1])
            rows.append(
                {
                    "titulo": _clean(fname.replace("_", " "))[:500],
                    "url": doc_url,
                    "origen": "ayto_impreso",
                }
            )
        for m in re.finditer(
            r'FORMULARIO[^<]{0,120}LICENCIA[^<]{0,120}</a>',
            html,
            re.I,
        ):
            title = _clean(re.sub(r"<[^>]+>", " ", m.group(0)))
            key = f"form:{title}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": title[:500],
                    "url": self.ayto_impresos,
                    "origen": "ayto_impreso",
                    "nota": "Formulario descargable en impresos y formularios",
                }
            )
        return rows

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
        if row.get("geom_geojson"):
            rec["geom_geojson"] = row["geom_geojson"]
            rec["geometry_source"] = row.get("geometry_source")
            rec["geometry_source_url"] = row.get("geometry_source_url")
            rec["coord_source"] = row.get("coord_source")
            rec["geometry_crs"] = row.get("geometry_crs", "EPSG:4326")
            centroid = geometry_centroid(row["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid
        else:
            self._attach_pgou_if_plan(rec)
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = (row.get("titulo") or "") + " " + (row.get("url") or "")
        if not RE_PROYECTO.search(blob) and row.get("origen") != "clm_arcgis":
            if row.get("origen") != "gmu_documento":
                return None
        return self._to_proyecto(row)

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"] + (row.get("titulo") or "")),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite / formulario licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": row.get("nota")
            or "Sin registro público de licencias concedidas; trámites e impresos",
            "origen": row.get("origen"),
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_requisitos_licencias() + self._collect_impresos_licencias():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        rows.append(
            {
                "id": _stable_id("lic", f"{self.gmu_base}/tablon-anuncios"),
                "fecha_concesion": None,
                "tipo": "tablón DNN",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Gerencia Urbanismo Cuenca",
                "url": f"{self.gmu_base}/tablon-anuncios",
                "source": "ayuntamiento",
                "nota": "Módulo tablaIP; sin anuncios visibles en el listado público actual",
                "origen": "gmu_tablon",
            }
        )
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "requisitos_impresos"}

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

        pgou = self._pgou_proyecto_row()
        if pgou:
            add(self._to_proyecto(pgou))
        for item in self._crawl_gmu_seeds():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "clm_pgou": 1 if pgou else 0,
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
