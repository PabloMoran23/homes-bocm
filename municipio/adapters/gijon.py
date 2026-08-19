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

BASE = "https://sedeelectronica.gijon.es"
SEDE_URBANISMO = (
    f"{BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=SEDE_URBANISMO"
)
SEDE_LICENCIAS = (
    f"{BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=SEDE_URBANISMO_LICENCIAS"
)
RPGUR_BASE = "https://www54.asturias.es/rpgur/action/publico"
MUNICIPIO = "Gijón"
ID_PREFIX = "gijon"

WFS_BASE = "http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows"
WFS_LAYER = "E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS"
WFS_MUNICIPIO_ID = "33024"

RE_RPGUR_ROW = re.compile(
    r'idInstrumento=(\d+).*?<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*'
    r'<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*'
    r'<td>\s*([^<]*?)\s*</td>',
    re.S,
)
RE_DETAIL_FIELD = re.compile(
    r'label_consulta2">\s*([^<:]+?)\s*:?\s*</label>.*?'
    r'(?:label_form_consulta_enlace">\s*<a[^>]*>([^<]+)</a>|'
    r'label_form_consulta">\s*([^<]+?)\s*</label>)',
    re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(r"(\d{4,6}[A-Z]/\d{4})")
RE_METADATA_ROWS = re.compile(
    r'metadata_(GJ_META_[A-Z_]+)\s*=\s*\{browse\s*:\s*(\{.*?\})\s*,\s*responsive',
    re.S,
)
RE_ROWS_JSON = re.compile(r'"rows":(\[.*?\]),"hasMoreRows"', re.S)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_proyecto(denominacion: str, clasificacion: str = "") -> str:
    blob = f"{denominacion} {clasificacion}".lower()
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "unidad de actuaci" in blob or "aua" in blob:
        return "unidad de actuación"
    if "normas" in blob and "provisional" in blob:
        return "normas provisionales"
    if "plan general" in blob or "pgou" in blob or "pgo " in blob:
        return "PGOU"
    if "plan especial" in blob or "pe " in blob:
        return "plan especial"
    if "plan parcial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "revisi" in blob:
        return "revisión planeamiento"
    if "convenio" in blob:
        return "convenio urbanístico"
    if clasificacion.lower() == "gestión":
        return "gestión urbanística"
    if clasificacion.lower() == "general":
        return "planeamiento general"
    if clasificacion.lower() == "desarrollo":
        return "planeamiento desarrollo"
    return "instrumento urbanístico"


class GijonAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede TAO + RPGUR Asturias; geometría parcial WFS visorrpgur (id_municipio=33024)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.rpgur_base = str(self.config.get("rpgur_base") or RPGUR_BASE).rstrip("/")
        self.rpgur_concejo_id = str(self.config.get("rpgur_concejo_id") or "24")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_BASE)
        self.wfs_layer = str(self.config.get("wfs_layer") or WFS_LAYER)
        self.wfs_municipio_id = str(self.config.get("wfs_municipio_id") or WFS_MUNICIPIO_ID)
        self._geom_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-gijon/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        if encoding == "iso-8859-1":
            return raw.decode("iso-8859-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_sede_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{BASE}/sta/CarpetaPublic/", href)

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
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        pass
        return rows

    def _load_geom_index(self) -> dict[str, dict[str, Any]]:
        if self._geom_index is not None:
            return self._geom_index
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": self.wfs_layer,
            "maxFeatures": "500",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": f"id_municipio={self.wfs_municipio_id}",
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        index: dict[str, dict[str, Any]] = {}
        try:
            data = self._fetch_json(url)
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                inv_id = props.get("Id._Inventario_Registro_Urbanístico")
                if inv_id is None or not isinstance(geom, dict):
                    continue
                key = str(inv_id)
                index[key] = {
                    "geom_geojson": geom,
                    "geometry_source": "portal_wfs",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            pass
        self._geom_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any], id_instrumento: str | int | None = None) -> None:
        if record_geometry(rec):
            return
        if id_instrumento is None:
            return
        geom = self._load_geom_index().get(str(id_instrumento))
        if geom:
            rec.update(geom)
            centroid = geometry_centroid(geom["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid

    def _parse_sede_metadata_rows(self, html: str, widget_name: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for m in RE_METADATA_ROWS.finditer(html):
            if m.group(1) != widget_name:
                continue
            rm = RE_ROWS_JSON.search(m.group(2))
            if not rm:
                continue
            try:
                data_rows = json.loads(rm.group(1))
            except json.JSONDecodeError:
                continue
            for item in data_rows:
                if not isinstance(item, dict):
                    continue
                cells = item.get("data") or []
                values = [_strip_html(str(c.get("value") or "")) for c in cells if isinstance(c, dict)]
                link = next(
                    (c.get("linkHref") for c in cells if isinstance(c, dict) and c.get("linkHref")),
                    None,
                )
                if values:
                    rows.append(
                        {
                            "values": values,
                            "link": self._abs_sede_url(link) if link else "",
                        }
                    )
        return rows

    def _fetch_rpgur_list(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        page = 1
        while page <= 25:
            params = {
                "method": "listPublico",
                "idConcejo": self.rpgur_concejo_id,
                "estado": "V",
                "primeraVez": "false",
                "page": str(page),
            }
            url = f"{self.rpgur_base}/busquedaConsulta?{urllib.parse.urlencode(params)}"
            try:
                html = self._fetch(url, encoding="iso-8859-1")
            except urllib.error.URLError:
                break
            page_rows = 0
            for m in RE_RPGUR_ROW.finditer(html):
                page_rows += 1
                rows.append(
                    {
                        "id": m.group(1),
                        "ambito": _strip_html(m.group(2)),
                        "concejo": _strip_html(m.group(3)),
                        "clasificacion": _strip_html(m.group(4)),
                        "denominacion": _strip_html(m.group(5)),
                        "expediente": _strip_html(m.group(6)),
                        "estado": _strip_html(m.group(7)),
                    }
                )
            if page_rows == 0 or f"page={page + 1}" not in html:
                break
            page += 1
        return rows

    def _fetch_rpgur_detail(self, id_instrumento: str) -> dict[str, str]:
        url = (
            f"{self.rpgur_base}/gestionConsulta"
            f"?method=retrieve&idInstrumento={urllib.parse.quote(id_instrumento)}"
        )
        fields: dict[str, str] = {}
        try:
            html = self._fetch(url, encoding="iso-8859-1")
        except urllib.error.URLError:
            return fields
        for m in RE_DETAIL_FIELD.finditer(html):
            label = _strip_html(m.group(1)).rstrip(":").strip()
            value = _strip_html(m.group(2) or m.group(3) or "").strip()
            if label and value:
                fields[label] = value
        return fields

    def _best_fecha(self, detail: dict[str, str], denominacion: str, expediente: str = "") -> str | None:
        for key in (
            "publicación BOPA aprobación definitiva",
            "acuerdo aprobación definitiva",
            "publicación BOPA aprobación inicial",
            "acuerdo aprobación inicial",
        ):
            parsed = _parse_fecha_dmy(detail.get(key, ""))
            if parsed:
                return parsed
        m = RE_EXPEDIENTE.search(expediente)
        if m:
            year = m.group(1).split("/")[-1]
            if year.isdigit():
                return f"{year}-01-01"
        return _iso_from_year(denominacion)

    def _collect_rpgur_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._fetch_rpgur_list():
            id_inst = item["id"]
            denominacion = item["denominacion"]
            expediente = item["expediente"]
            detail = self._fetch_rpgur_detail(id_inst)
            url = (
                f"{self.rpgur_base}/gestionConsulta"
                f"?method=retrieve&idInstrumento={id_inst}"
            )
            titulo = detail.get("Denominación", denominacion) or denominacion
            rec = {
                "id": _stable_id("proy", f"rpgur:{id_inst}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": self._best_fecha(detail, titulo, expediente),
                "tipo": _tipo_proyecto(titulo, item.get("clasificacion", "")),
                "url": url,
                "source": "ayuntamiento",
                "origen": "rpgur",
                "expediente": expediente or detail.get("Expediente"),
                "estado": item.get("estado") or detail.get("Estado"),
                "clasificacion": item.get("clasificacion"),
                "id_instrumento": id_inst,
            }
            self._attach_geometry(rec, id_inst)
            rows.append(rec)
        return rows

    def _collect_sede_infopublica(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(SEDE_URBANISMO)
        except urllib.error.URLError:
            return rows
        for item in self._parse_sede_metadata_rows(
            html, "GJ_META_URBANISMO_PLANEAMIENTO_INFOPUBLICA"
        ):
            values = item["values"]
            expediente = values[0] if values else ""
            titulo = values[1] if len(values) > 1 else expediente
            link = item.get("link") or SEDE_URBANISMO
            rec = {
                "id": _stable_id("proy", f"sede-ip:{expediente}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _parse_fecha_dmy(expediente) or _iso_from_year(expediente),
                "tipo": _tipo_proyecto(titulo),
                "url": link,
                "source": "ayuntamiento",
                "origen": "sede_infopublica",
                "expediente": expediente,
            }
            m = RE_EXPEDIENTE.search(expediente)
            if m:
                rec["fecha"] = f"{m.group(1).split('/')[-1]}-01-01"
            rows.append(rec)
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            html = self._fetch(SEDE_LICENCIAS)
        except urllib.error.URLError:
            html = ""

        for item in self._parse_sede_metadata_rows(html, "GJ_META_URBANISMO_LICENCIAS"):
            values = item["values"]
            titulo = values[0] if values else "Trámite licencia"
            link = item.get("link") or SEDE_LICENCIAS
            rec_id = _stable_id("lic", link or titulo)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": link,
                    "source": "ayuntamiento",
                    "nota": "Catálogo TECREA; sin listado público de concesiones",
                }
            )

        urbanismo_url = SEDE_URBANISMO
        info_id = _stable_id("lic", urbanismo_url)
        if info_id not in seen:
            seen.add(info_id)
            rows.append(
                {
                    "id": info_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Urbanismo — sede electrónica",
                    "url": urbanismo_url,
                    "source": "ayuntamiento",
                    "nota": "Instrumentos planeamiento y gestión en sede TAO",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_informativos"}

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

        for rec in self._collect_rpgur_proyectos():
            add(rec)
        for rec in self._collect_sede_infopublica():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "rpgur": sum(1 for r in rows if r.get("origen") == "rpgur"),
            "sede_infopublica": sum(1 for r in rows if r.get("origen") == "sede_infopublica"),
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
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
