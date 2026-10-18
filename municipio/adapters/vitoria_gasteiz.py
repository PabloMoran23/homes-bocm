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

BASE = "https://www.vitoria-gasteiz.org"
SEDE = "https://sedeelectronica.vitoria-gasteiz.org"
MUNICIPIO = "Vitoria-Gasteiz"
ID_PREFIX = "vitoria-gasteiz"

EXPEDIENTES_TRAMITACION = (
    f"{BASE}/wb021/was/contenidoAction.do?idioma=es&uid=u_16dc2b57_134cb3b30bd__7fe9"
)
PLANEAMIENTO_DESARROLLO = (
    f"{BASE}/wb021/was/contenidoAction.do?idioma=es&uid=u6bf57c84_13f2c50cf68__7fa9"
)
CONVENIOS_URBANISTICOS = (
    f"{BASE}/wb021/was/contenidoAction.do?idioma=es&uid=u8d5a2c5_13f83da3e15__7fc4"
)

ARCGIS_PROYECTO_OBRA = (
    f"{BASE}/arcgis/rest/services/internet/10_u15grupo04/MapServer/10"
)
ARCGIS_PGOU_AMBITOS = (
    f"{BASE}/arcgis/rest/services/internet/10_pgou_wms_6_7_omv/MapServer/0"
)

SEDE_LICENCIA_TRAMITES: tuple[tuple[str, str], ...] = (
    ("Licencia de obra menor", f"{SEDE}/portal/es/w/licencia-de-obra-menor"),
    (
        "Solicitud de licencia de obra mayor para reformas",
        f"{SEDE}/portal/es/w/solicitud-de-licencia-de-obra-mayor-para-reformas-2407269",
    ),
    (
        "Información urbanística / consulta urbanística",
        f"{SEDE}/portal/es/w/informacion-urbanistica-consulta-urbanistica",
    ),
)

RE_ODT = re.compile(r"<!--ODT:start-->(.*?)<!--ODT:end-->", re.S | re.I)
RE_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_TAG = re.compile(r"<[^>]+>")
RE_AMBITO_CODE = re.compile(r"\b([AS]-\d{1,3}(?:\.\d+)?|[A-Z]{2,}-\w+)\b")
RE_OA_CODE = re.compile(r"\bOA\s*([\d.]+)\b", re.I)
RE_SECTOR = re.compile(r"sector\s+(\d+)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\-]+)", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_ADJUNTO_PDF = re.compile(
    r'href="([^"]+accionWe001=adjunto[^"]+nombre=[^"]+\.pdf)"', re.I
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = RE_TAG.sub(" ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _arcgis_ms_date(value: Any) -> str | None:
    if value in (None, "", 0):
        return None
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%d")


def _fecha_from_text(text: str) -> str | None:
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    blob = (title or "").lower()
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob or "peri" in blob:
        return "plan especial"
    if "modificaci" in blob and "plan" in blob:
        return "modificación de planeamiento"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "pgou" in blob:
        return "PGOU"
    return "planeamiento urbanístico"


def _esri_rings_to_geojson(geometry: dict[str, Any]) -> dict[str, Any] | None:
    rings: list[list[list[float]]] = []
    for ring in geometry.get("rings") or []:
        if isinstance(ring, list) and len(ring) >= 3:
            pts = [[float(p[0]), float(p[1])] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
            if len(pts) >= 3:
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                if len(pts) >= 4:
                    rings.append(pts)
    if not rings:
        x = geometry.get("x")
        y = geometry.get("y")
        if x is not None and y is not None:
            return {"type": "Point", "coordinates": [float(x), float(y)]}
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}


class VitoriaGasteizAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal j38 (PGOU expedientes) + ArcGIS Proyecto obra / ámbitos PGOU + sede trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.expedientes_url = str(self.config.get("expedientes_url") or EXPEDIENTES_TRAMITACION)
        self.planeamiento_url = str(
            self.config.get("planeamiento_desarrollo_url") or PLANEAMIENTO_DESARROLLO
        )
        self.convenios_url = str(self.config.get("convenios_url") or CONVENIOS_URBANISTICOS)
        geom_cfg = self.config.get("geometry") or {}
        self.arcgis_obra = str(geom_cfg.get("obra_layer") or ARCGIS_PROYECTO_OBRA).rstrip("/")
        self.arcgis_ambitos = str(geom_cfg.get("ambitos_layer") or ARCGIS_PGOU_AMBITOS).rstrip("/")
        self._ambitos_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-vitoria-gasteiz/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        text = self._fetch(url)
        return json.loads(text)

    def _abs(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{BASE}/", href.replace("&amp;", "&")))

    def _arcgis_query_page(
        self,
        layer: str,
        *,
        where: str = "1=1",
        out_fields: str = "*",
        offset: int = 0,
        page_size: int = 500,
    ) -> dict[str, Any]:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
        }
        url = f"{layer}/query?{urllib.parse.urlencode(params)}"
        return self._fetch_json(url)

    def _arcgis_all_features(self, layer: str, out_fields: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            try:
                data = self._arcgis_query_page(layer, out_fields=out_fields, offset=offset)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            feats = data.get("features") or []
            if not feats:
                break
            rows.extend(feats)
            if not data.get("exceededTransferLimit", len(feats) >= 500):
                break
            offset += len(feats)
        return rows

    def _load_ambitos(self) -> list[dict[str, Any]]:
        if self._ambitos_cache is not None:
            return self._ambitos_cache
        items: list[dict[str, Any]] = []
        for feat in self._arcgis_all_features(self.arcgis_ambitos, "AMBITO,NOMBRE,TIPO"):
            attrs = feat.get("attributes") or {}
            geom = _esri_rings_to_geojson(feat.get("geometry") or {})
            if not geom:
                continue
            ambito = str(attrs.get("AMBITO") or "").strip()
            nombre = str(attrs.get("NOMBRE") or "").strip()
            items.append(
                {
                    "ambito": ambito.upper(),
                    "nombre": nombre.upper(),
                    "geom": geom,
                    "attrs": attrs,
                }
            )
        self._ambitos_cache = items
        return items

    def _match_ambito_geometry(self, title: str, code_hint: str | None = None) -> dict[str, Any] | None:
        items = self._load_ambitos()
        if not items:
            return None

        hints: list[str] = []
        if code_hint:
            hints.append(code_hint.upper().strip())
        for m in RE_AMBITO_CODE.finditer(title or ""):
            hints.append(m.group(1).upper())
        oa = RE_OA_CODE.search(title or "")
        if oa:
            hints.append(f"OA {oa.group(1)}")
            hints.append(oa.group(1))
        sec = RE_SECTOR.search(title or "")
        if sec:
            hints.append(f"SECTOR {sec.group(1)}")
            hints.append(sec.group(2).upper())

        title_u = (title or "").upper()
        best: tuple[int, dict[str, Any]] | None = None
        for item in items:
            score = 0
            amb = item["ambito"]
            nom = item["nombre"]
            for h in hints:
                if h and (h == amb or h in amb or amb in h):
                    score += 50
                if h and h in nom:
                    score += 30
            for token in re.findall(r"[A-ZÁÉÍÓÚÑ]{4,}", title_u):
                if token in nom or token in amb:
                    score += 8
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, item)
        if not best or best[0] < 8:
            return None
        item = best[1]
        query_url = (
            f"{self.arcgis_ambitos}/query?where=AMBITO%3D%27"
            f"{urllib.parse.quote(item['ambito'])}%27&outSR=4326&f=json&returnGeometry=true"
        )
        return {
            "geom_geojson": item["geom"],
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _first_pdf(self, page_url: str) -> str | None:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return None
        m = RE_ADJUNTO_PDF.search(html)
        if not m:
            return None
        return self._abs(m.group(1))

    def _parse_list_links(self, html: str, *, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        odt = RE_ODT.search(html)
        block = odt.group(1) if odt else html
        for li in RE_LI.findall(block):
            hrefs = RE_HREF.findall(li)
            if not hrefs:
                continue
            page_url = None
            for h in hrefs:
                if "contenidoAction" in h:
                    page_url = self._abs(h)
                    break
            if not page_url:
                continue
            title = _strip_html(li)
            if len(title) < 8:
                continue
            code_hint = None
            m_code = RE_AMBITO_CODE.search(li)
            if m_code:
                code_hint = m_code.group(1)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", page_url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": _fecha_from_text(title),
                "tipo": _proyecto_tipo(title),
                "url": page_url,
                "source": "ayuntamiento",
                "origen": origen,
            }
            geom = self._match_ambito_geometry(title, code_hint)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(rec["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            pdf = self._first_pdf(page_url)
            if pdf:
                rec["pdf_url"] = pdf
            rows.append(rec)
        return rows

    def _collect_expedientes_tramitacion(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.expedientes_url)
        except urllib.error.URLError:
            return []
        return self._parse_list_links(html, origen="expedientes_tramitacion")

    def _collect_planeamiento_desarrollo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.planeamiento_url)
        except urllib.error.URLError:
            return []
        return self._parse_list_links(html, origen="planeamiento_desarrollo")

    def _collect_convenios(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.convenios_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for li in RE_LI.findall(html):
            if "convenio" not in li.lower() and "contenidoAction" not in li:
                continue
            hrefs = [h for h in RE_HREF.findall(li) if "contenidoAction" in h]
            if not hrefs:
                continue
            url = self._abs(hrefs[0])
            title = _strip_html(li)
            if len(title) < 6:
                continue
            rec = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": _fecha_from_text(title),
                "tipo": "convenio urbanístico",
                "url": url,
                "source": "ayuntamiento",
                "origen": "convenios",
            }
            geom = self._match_ambito_geometry(title)
            if geom:
                rec.update(geom)
                cen = geometry_centroid(rec["geom_geojson"])
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencias_obra_arcgis(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._arcgis_all_features(
            self.arcgis_obra,
            "CODIGO,TITULO,TIPO,CALLE,ZONA,FECHA_ELAB,FECHA_ADJU,FEC_INI_OB,FEC_BAJA",
        ):
            attrs = feat.get("attributes") or {}
            if attrs.get("FEC_BAJA"):
                continue
            codigo = str(attrs.get("CODIGO") or "").strip()
            titulo = str(attrs.get("TITULO") or "").strip()
            if not titulo:
                continue
            fecha = (
                _arcgis_ms_date(attrs.get("FECHA_ADJU"))
                or _arcgis_ms_date(attrs.get("FEC_INI_OB"))
                or _arcgis_ms_date(attrs.get("FECHA_ELAB"))
            )
            geom = _esri_rings_to_geojson(feat.get("geometry") or {})
            rec: dict[str, Any] = {
                "id": _stable_id("lic", codigo or titulo),
                "fecha_concesion": fecha,
                "tipo": str(attrs.get("TIPO") or "proyecto de obra")[:120],
                "distrito": str(attrs.get("ZONA") or attrs.get("CALLE") or "")[:200] or None,
                "titulo": titulo[:500],
                "source": "ayuntamiento",
                "origen": "arcgis_proyecto_obra",
            }
            if geom:
                query_url = (
                    f"{self.arcgis_obra}/query?where=CODIGO%3D%27"
                    f"{urllib.parse.quote(codigo.replace(chr(39), chr(39)*2))}%27"
                    "&outSR=4326&f=json&returnGeometry=true"
                )
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_source"] = "portal_visor_arcgis"
                rec["geometry_source_url"] = query_url
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for title, url in SEDE_LICENCIA_TRAMITES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_tramites",
                    "nota": "Página informativa; sin listado público de concesiones",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        rows = self._collect_licencias_obra_arcgis() + self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "arcgis_obra": sum(1 for r in rows if r.get("origen") == "arcgis_proyecto_obra"),
            "with_geometry": with_geom,
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_obra_arcgis() + self._collect_licencias_tramites():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in (
            self._collect_expedientes_tramitacion()
            + self._collect_planeamiento_desarrollo()
            + self._collect_convenios()
        ):
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "expedientes_tramitacion": sum(
                1 for r in rows if r.get("origen") == "expedientes_tramitacion"
            ),
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
        return {**stats, "added": max(0, after - before)}
