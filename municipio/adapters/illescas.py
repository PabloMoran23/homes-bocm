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
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://illescas.sedelectronica.es"
MUNICIPIO = "Illescas"
ID_PREFIX = "illescas"

CLM_PLANEAMIENTO_LAYER = (
    "https://geoservicios.castillalamancha.es/arcgis/rest/services/"
    "Vector/Planeamiento_Municipal/MapServer/0"
)
COD_INE = "45081"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|cedula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pom\b|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|urbanizaci[oó]n|programa de actuaci|sector|sub so|sau-|pau |"
    r"estatutos.*conservaci|entidad urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|empleo p[uú]blico|pleno|junta de gobierno|bolsa de trabajo|"
    r"subvencion|proceso selectivo|oposici[oó]n|comida a domicilio)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_PREVIEW = re.compile(
    r'href="(?:https://illescas\.sedelectronica\.es)?(/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_DOSSIER_LINK = re.compile(
    r'href="((?:https://illescas\.sedelectronica\.es)?/(?:citizen-service|catalog)/[^"]+)"'
    r'[^>]*>([^<]{5,200})</a>',
    re.I,
)
RE_DOSSIER_SKIP = re.compile(
    r"(?i)(polic[ií]a local|medioambiente_|cens[oó] canino|sancionador|tr[aá]fico|"
    r"informaci[oó]n p[uú]blica por los ciudadanos|consulta de expedientes|"
    r"auto-?taxi|ocupaci[oó]n del dominio|terrazas|atracciones|puesto de venta|"
    r"animal potencialmente peligroso|acceso a la informaci[oó]n p[uú]blica)",
)
RE_DOSSIER_PROYECTO = re.compile(
    r"(?i)(planeamiento|actuaci[oó]n urban|compensaci[oó]n|reparcel|convenio urban|"
    r"aprobaci[oó]n.*planeamiento|modificaci[oó]n.*planeamiento|certificado.*urban|"
    r"informe urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(y.group(1))
        for y in re.finditer(r"\b((?:19|20)\d{2})\b", text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual POM"
    if "reparcel" in n:
        return "reparcelación"
    if "convenio" in n:
        return "convenio urbanístico"
    if "programa de actuaci" in n or "pau" in n:
        return "programa de actuación urbanizadora"
    if "informaci" in n:
        return "información pública"
    if "pom" in n or "plan de ordenaci" in n or "pgou" in n:
        return "POM / planeamiento"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class IllescasAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón + transparencia) + ArcGIS CLM POM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        geom_cfg = self.config.get("geometry") or {}
        self.clm_layer = str(geom_cfg.get("arcgis_layer_url") or CLM_PLANEAMIENTO_LAYER)
        self.cod_ine = str(geom_cfg.get("cod_ine") or COD_INE)
        self._pgou_geom: dict[str, Any] | None = None
        self._pgou_meta: dict[str, Any] | None = None
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-illescas/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-illescas/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

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

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tr in RE_BOARD_ROW.findall(html):
            cells = RE_BOARD_CELL.findall(tr)
            if not cells:
                continue
            row = {label: _strip_html(val) for label, val in cells}
            link_m = re.search(r"preview-document/([a-f0-9-]+)", tr, re.I)
            if not link_m:
                continue
            uuid = link_m.group(1)
            if uuid in seen:
                continue
            seen.add(uuid)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else row.get("Documento", "")
            titulo = (titulo or row.get("Descripción", ""))[:500]
            rows.append(
                {
                    "titulo": titulo,
                    "expediente": row.get("Expediente", ""),
                    "procedimiento": row.get("Procedimiento", ""),
                    "categoria": row.get("Categoría", ""),
                    "descripcion": row.get("Descripción", ""),
                    "fecha": _parse_fecha_dmy(row.get("Fecha de Publicación", "")),
                    "url": f"{self.sede_base}/preview-document/{uuid}",
                    "pdf_url": f"{self.sede_base}/preview-document/{uuid}",
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=60)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_transparency_index(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url, timeout=45)
        except urllib.error.URLError:
            return []
        m = re.search(
            r"URBANISMO y CONVENIOS URBANISTICOS.*?linkExtraInfo\">\s*\(\s*(\d+)\s*\)",
            html,
            re.I | re.S,
        )
        count = m.group(1) if m else "?"
        return [
            {
                "titulo": (
                    "Portal de transparencia — Urbanismo, convenios urbanísticos, "
                    f"obras públicas y medio ambiente ({count} documentos)"
                ),
                "fecha": None,
                "url": self.transparency_url,
                "tipo": "catálogo transparencia urbanismo",
                "origen": "sede_transparencia",
            }
        ]

    def _collect_dossier_links(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.dossier_url, timeout=35)
        except urllib.error.URLError:
            return rows
        for href, label in RE_DOSSIER_LINK.findall(html):
            titulo = _strip_html(label)
            if RE_DOSSIER_SKIP.search(titulo):
                continue
            url = self._abs_sede(href)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": titulo[:500], "url": url})
        return rows

    def _collect_dossier_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self._collect_dossier_links():
            if not RE_DOSSIER_PROYECTO.search(item["titulo"]):
                continue
            out.append({**item, "origen": "sede_dossier", "tipo": "trámite planeamiento"})
        return out

    def _collect_dossier_licencias(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self._collect_dossier_links():
            if not RE_LICENCIA.search(item["titulo"]):
                continue
            out.append(item)
        return out

    def _fetch_clm_pom(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if self._pgou_geom is not None:
            return self._pgou_geom, self._pgou_meta
        where = f"COD_INE='{self.cod_ine}'"
        params = urllib.parse.urlencode(
            {
                "where": where,
                "outFields": "NOM_PLAN,PLAN_,FECHA_APRO,DESCARGA,MUNICIPIO",
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

    def _pom_proyecto_row(self) -> dict[str, Any] | None:
        geom, meta = self._fetch_clm_pom()
        if not geom or not meta:
            return None
        nom = str(meta.get("nom_plan") or "Plan de Ordenación Municipal")
        url = str(
            meta.get("descarga")
            or f"{self.transparency_url} (documentación urbanística)"
        )
        rec: dict[str, Any] = {
            "titulo": f"{nom} — {MUNICIPIO} (CLM, INE {self.cod_ine})",
            "fecha": None,
            "url": url,
            "tipo": "POM",
            "origen": "clm_arcgis",
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": meta.get("geometry_source_url"),
            "coord_source": "portal_geometry_centroid",
        }
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid
        return rec

    def _attach_pom_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = (rec.get("titulo") or "").lower()
        if not any(k in blob for k in ("pom", "pgou", "plan de ordenaci", "planeamiento municipal")):
            return
        geom, meta = self._fetch_clm_pom()
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = (meta or {}).get("geometry_source_url")
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec.setdefault("lat", centroid[0])
            rec.setdefault("lon", centroid[1])

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede espublico gestiona",
                "origen": "sede_board",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — urbanismo y vivienda",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Trámites informativos; concesiones en tablón cuando se publiquen",
                "origen": "sede_dossier",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — sección urbanismo",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Documentación urbanística y convenios (carpeta 7)",
                "origen": "sede_transparencia",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("urban", "licencia", "planeam", "obra", "disposiciones")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(
            " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "descripcion"))
        ):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = item["titulo"]
        url = item.get("url") or self.sede_base
        blob = f"{titulo} {item.get('procedimiento', '')} {item.get('tipo', '')}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url + titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": item.get("fecha") or _fecha_from_blob(titulo),
            "tipo": item.get("tipo") or _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("expediente"):
            rec["expte"] = item["expediente"]
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("geom_geojson"):
            rec.update(
                {
                    k: item[k]
                    for k in (
                        "geom_geojson",
                        "geometry_source",
                        "geometry_source_url",
                        "coord_source",
                        "geometry_crs",
                        "lat",
                        "lon",
                    )
                    if k in item
                }
            )
        else:
            self._attach_pom_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._item_to_proyecto(row)

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
        for item in self._collect_dossier_licencias():
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "nota": "Formulario sede; sin registro histórico de concesiones",
                "origen": "sede_dossier",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "origen": "sede_espublico"}

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if not rec or rec["id"] in seen:
                return
            seen.add(rec["id"])
            rows.append(rec)

        pom = self._pom_proyecto_row()
        if pom:
            add(self._item_to_proyecto(pom))

        for item in self._collect_transparency_index():
            add(self._item_to_proyecto(item))

        for item in self._collect_dossier_proyectos():
            add(self._item_to_proyecto(item))

        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "clm": sum(1 for r in rows if r.get("origen") == "clm_arcgis"),
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
