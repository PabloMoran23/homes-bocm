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

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://puebladelasierra.es"
SEDE_BASE = "https://puebladelasierra.sedelectronica.es"
MUNICIPIO = "Puebla de la Sierra"
ID_PREFIX = "puebla-de-la-sierra"
WFS_MUNICIPIO = "PUEBLA DE LA SIERRA"
SITCM_VISOR_URL = "http://idem.madrid.org/cartografia/sitcm/html/visor.htm"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ayuntamiento/ordenanzas/",
    f"{WP_BASE}/ayuntamiento/descarga-de-documentos/",
]

LICENCIA_OBRA_MENOR_PDF = (
    f"{WP_BASE}/wp-content/uploads/2025/06/SOLICITUD-PARA-LICENCIA-DE-OBRA-MENOR-2.pdf"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|ordenanza.*urban|procedimiento.*urban|desbroce|solar|bocm|edicto|bando|"
    r"tasa.*urban|servicios urban|limpieza de solar|"
    r"\b(?:P|UE|UA|AD|AN|AI|PAU|S)-[\w\d-]+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|igualdad|casa de ni[nñ]os|admisi[oó]n|"
    r"calendario fiscal|recaudaci[oó]n|cementerio|apicola|audiovisual|veh[ií]culo|"
    r"estacionamiento discapacidad|fotocopiadora|basura|rsu|piscina|deportiv|"
    r"empadronamiento|cambio.residencia|volante.certificado)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_BOCM_DATE = re.compile(r"BOCM[- ]?(\d{2})\.(\d{2})\.(\d{2,4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://puebladelasierra\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://(?:www\.)?puebladelasierra\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        year = int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bue-\d+\b", n):
        return "unidad de ejecución"
    if re.search(r"\bua-\d+\b", n):
        return "unidad de actuación"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan general" in n or "planeamiento" in n:
        return "planeamiento"
    if "procedimiento" in n and "urban" in n:
        return "ordenanza urbanística"
    if "tasa" in n and "urban" in n:
        return "ordenanza fiscal urbanística"
    if "desbroce" in n or "solar" in n:
        return "ordenanza desbroce"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


class PueblaDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Astra + sede espublico gestiona + ámbitos SITCM WFS (UE-1..UE-3)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.descarga_url = str(
            self.config.get("descarga_url") or f"{self.wp_base}/ayuntamiento/descarga-de-documentos/"
        )
        self.ordenanzas_url = str(
            self.config.get("ordenanzas_url") or f"{self.wp_base}/ayuntamiento/ordenanzas/"
        )
        self.licencia_obra_menor_pdf = str(
            self.config.get("licencia_obra_menor_pdf") or LICENCIA_OBRA_MENOR_PDF
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self.wfs_url = str(
            (self.config.get("geometry") or {}).get("wfs_url")
            or "https://idem.comunidad.madrid/geoserver3/ows"
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        ctx = self._ssl_ctx if use_insecure and "sedelectronica" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url, insecure=False))

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "sitcm:VPLA_V_AMBITO",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        self._wfs_cache = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=50)
        return self._wfs_cache

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, insecure=True)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            if cells[0] in ("Documento", "Expediente"):
                continue

            documento = cells[0] if len(cells) > 0 else ""
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            categoria = cells[3] if len(cells) > 3 else ""
            descripcion = cells[4] if len(cells) > 4 else ""
            fecha_raw = cells[5] if len(cells) > 5 else ""

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
            blob = f"{documento} {expediente} {procedimiento} {categoria} {descripcion} {titulo}"
            if RE_EXCLUDE.search(blob):
                continue

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "blob": blob,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, insecure=False)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                raw = m.group(1)
                pdf = raw if raw.startswith("http") else urllib.parse.urljoin(f"{self.wp_base}/", raw)
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{name} {page_url}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": name.replace("-", " ").replace("_", " ")[:500],
                        "url": pdf,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_url(pdf),
                        "origen": "web_pdf",
                        "page_url": page_url,
                    }
                )
        return rows

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for feat in self._load_wfs_ambitos():
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Publicación de edictos y licencias cuando proceda",
                "origen": "tablon_sede",
            },
            {
                "id": _stable_id("lic", self.descarga_url),
                "fecha_concesion": None,
                "tipo": "licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Descarga de documentos — solicitudes urbanísticas",
                "url": self.descarga_url,
                "source": "ayuntamiento",
                "nota": "Formularios de licencia de obra menor y trámites",
                "origen": "web_descarga",
            },
            {
                "id": _stable_id("lic", self.licencia_obra_menor_pdf),
                "fecha_concesion": "2025-06-01",
                "tipo": "solicitud licencia obra menor",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitud para licencia de obra menor (PDF)",
                "url": self.licencia_obra_menor_pdf,
                "source": "ayuntamiento",
                "nota": "Formulario publicado en web municipal (jun 2025)",
                "origen": "web_pdf",
            },
        ]

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if rec.get("geom_geojson"):
            return
        titulo = rec.get("titulo") or ""
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            f"{self.wfs_url}?service=WFS&typeName=sitcm:VPLA_V_AMBITO"
            f"&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if meta.get("ambito_name"):
            rec["ambito_sit"] = meta["ambito_name"]
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("page_url"):
            rec["page_url"] = row["page_url"]
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
        for item in self._collect_web_pdfs():
            if not RE_LICENCIA.search(item["titulo"]):
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "formulario licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item.get("origen"),
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen", "").startswith(("tablon", "sede", "web"))),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_web_pdfs():
            if RE_LICENCIA.search(item["titulo"]):
                existing[_stable_id("lic", item["url"])] = {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": "formulario licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": item.get("origen"),
                }
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for item in self._collect_web_pdfs():
            add(self._pdf_to_proyecto(item))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
