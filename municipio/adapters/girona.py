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
from municipio.geometry import geometry_centroid, has_area_geometry, record_geometry

WEB_BASE = "https://web.girona.cat"
SEU_BASE = "https://seu.girona.cat"
PLAN_PATH = "/urbanisme/planejament/pgou"
PROXY_QS = (
    "p_p_id=ProxyController_INSTANCE_TFYoJoQx4j8W"
    "&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
    "&_ProxyController_INSTANCE_TFYoJoQx4j8W_rformx2=1?vigent=1"
)
UMAT_VISOR = "https://umat.girona.cat/vu/mapa/planejament/"
ARCGIS_IDENTIFY = (
    "https://terra.girona.cat/servergis/rest/services/planejament/Planejament/MapServer/identify"
)
MUNICIPIO = "Girona"
ID_PREFIX = "girona"

DEFAULT_CATEGORIES = [
    "68", "37", "44", "38", "39", "36", "1120", "1014", "1121", "41", "42", "43", "999", "40", "904", "902", "903"
]

TRAMITES_URBANISMO_URL = f"{SEU_BASE}/portal/girona_es/tramits/urbanisme/index.html"
EXPOSICION_URL = f"{SEU_BASE}/portal/girona_es/expedients_exposicio/index.html"

RE_IDCAT = re.compile(r"idCat=(\d+)")
RE_LIST_ROW = re.compile(
    r"<tr><td><span>(\d{4})</span></td><td><a href=\"javascript:\s*fitxaPlanejament\('(\d+)'\)[^>]*>"
    r"<b>(.*?)</b>.*?</td><td><span>([^<]*)</span>",
    re.I | re.S,
)
RE_H2_CAT = re.compile(r"<h2>([^<]+)</h2>", re.I)
RE_H3_TITLE = re.compile(r"<h3>(?!class)([^<]+)</h3>", re.I)
RE_EXP_AJUNT = re.compile(
    r"expedient de l'Ajuntament:\s*<b>([^<]+)</b>|expedient de l&#39;Ajuntament:\s*<b>([^<]+)</b>",
    re.I,
)
RE_EXP_URB = re.compile(
    r"expedient d'Urbanisme:\s*<b>([^<]+)</b>|expedient d&#39;Urbanisme:\s*<b>([^<]+)</b>",
    re.I,
)
RE_UMAT_Q = re.compile(
    r"umat\.girona\.cat/vu/mapa/planejament/\?q=([\d.]+)\s+([\d.]+)",
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'<a href="(/portal/girona_es/serveis/e-registre/AaZ/\d+\.html)">\s*([^<]+)',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


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
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(titulo: str, categoria: str) -> str:
    n = f"{titulo} {categoria}".lower()
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual PGOU"
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "plan parcial" in n or "ppu" in n or "plans parcials" in n:
        return "plan parcial"
    if "pmu" in n or "millora urbana" in n:
        return "plan mejora urbana"
    if "plan especial" in n or " pe " in f" {n} ":
        return "plan especial"
    if "reparcel" in n:
        return "reparcelación"
    if "conveni" in n:
        return "convenio urbanístico"
    return "planeamiento urbanístico"


def _esri_rings_to_geojson(rings: list) -> dict[str, Any]:
    return {"type": "Polygon", "coordinates": rings}


class GironaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay planejament PGOU (ProxyController) + seu OpenCMS + UMAT/ArcGIS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.category_ids = [str(x) for x in (self.config.get("category_ids") or DEFAULT_CATEGORIES)]
        self.max_geometry_details = int(self.config.get("max_geometry_details", 40))
        self.geometry_min_year = int(self.config.get("geometry_min_year", 2020))
        self._identify_layer = str(self.config.get("arcgis_identify_layer", "27"))

    def _plan_url(self, *, id_cat: str | None = None, id_reg: str | None = None) -> str:
        qs = PROXY_QS
        if id_cat:
            qs += f"&idCat={id_cat}"
        if id_reg and id_cat:
            qs += f"&idReg={id_reg}"
        return f"{self.web_base}{PLAN_PATH}?{qs}"

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-girona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 60) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-girona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _discover_categories(self) -> list[str]:
        try:
            html = self._fetch(self._plan_url())
        except urllib.error.URLError:
            return self.category_ids
        found = sorted(set(RE_IDCAT.findall(html)), key=int)
        return found or self.category_ids

    def _parse_category_listing(self, id_cat: str, html: str) -> tuple[str, list[dict[str, Any]]]:
        h2m = RE_H2_CAT.search(html)
        categoria = _strip_html(h2m.group(1)) if h2m else f"Categoría {id_cat}"
        items: list[dict[str, Any]] = []
        for m in RE_LIST_ROW.finditer(html):
            year, id_reg, titulo_raw, fecha_aprob = (
                int(m.group(1)),
                m.group(2),
                m.group(3),
                m.group(4),
            )
            titulo = _strip_html(titulo_raw)
            items.append(
                {
                    "id_reg": id_reg,
                    "id_cat": id_cat,
                    "categoria": categoria,
                    "titulo": titulo,
                    "fecha_aprobacion": _parse_fecha_dmy(fecha_aprob),
                    "year": year,
                    "url": self._plan_url(id_cat=id_cat, id_reg=id_reg),
                }
            )
        return categoria, items

    def _parse_detail(self, html: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        h3 = RE_H3_TITLE.search(html)
        if h3:
            out["titulo"] = _strip_html(h3.group(1))
        m_aj = RE_EXP_AJUNT.search(html)
        if m_aj:
            out["expediente_ajuntament"] = (m_aj.group(1) or m_aj.group(2) or "").strip()
        m_urb = RE_EXP_URB.search(html)
        if m_urb:
            out["expediente_urbanisme"] = (m_urb.group(1) or m_urb.group(2) or "").strip()
        m_um = RE_UMAT_Q.search(html)
        if m_um:
            out["umat_lat"] = float(m_um.group(1))
            out["umat_lon"] = float(m_um.group(2))
            out["geometry_source_url"] = (
                f"{UMAT_VISOR}?q={m_um.group(1)}%20{m_um.group(2)}&zoom=18"
            )
        for pm in re.finditer(r'class="planTxt"[^>]*>(.*?)</p>', html, re.I | re.S):
            txt = _strip_html(pm.group(1))
            fd = _parse_fecha_dmy(txt)
            if fd and "fecha" not in out:
                out["fecha"] = fd
        return out

    def _arcgis_polygon_at(self, lat: float, lon: float) -> tuple[dict[str, Any] | None, str | None]:
        pad = 0.015
        params = {
            "f": "json",
            "geometry": json.dumps({"x": lon, "y": lat}),
            "geometryType": "esriGeometryPoint",
            "sr": "4326",
            "layers": f"all:{self._identify_layer}",
            "tolerance": "8",
            "mapExtent": f"{lon - pad},{lat - pad},{lon + pad},{lat + pad}",
            "imageDisplay": "800,800,96",
            "returnGeometry": "true",
        }
        url = f"{ARCGIS_IDENTIFY}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None, None
        for res in data.get("results") or []:
            geom = res.get("geometry") or {}
            rings = geom.get("rings")
            if rings:
                return _esri_rings_to_geojson(rings), url
        return None, url

    def _attach_geometry(self, rec: dict[str, Any], detail: dict[str, Any]) -> None:
        lat = detail.get("umat_lat")
        lon = detail.get("umat_lon")
        if lat is None or lon is None:
            return
        poly, identify_url = self._arcgis_polygon_at(lat, lon)
        if poly:
            rec["geom_geojson"] = poly
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_axis_order"] = "xy"
            rec["geometry_source"] = "portal_visor_arcgis"
            rec["geometry_source_url"] = identify_url or detail.get("geometry_source_url")
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(poly)
            if cen:
                rec["lat"], rec["lon"] = cen

    def _collect_planejament(self) -> list[dict[str, Any]]:
        categories = self._discover_categories()
        raw_items: list[dict[str, Any]] = []
        for id_cat in categories:
            try:
                html = self._fetch(self._plan_url(id_cat=id_cat))
            except urllib.error.URLError:
                continue
            _, items = self._parse_category_listing(id_cat, html)
            raw_items.extend(items)

        detail_budget = self.max_geometry_details
        rows: list[dict[str, Any]] = []
        for item in raw_items:
            titulo = item["titulo"]
            categoria = item["categoria"]
            fecha = item.get("fecha_aprobacion")
            year = item.get("year") or 0
            detail: dict[str, Any] = {}
            want_detail = detail_budget > 0 and (year >= self.geometry_min_year or not fecha)
            if want_detail:
                try:
                    html = self._fetch(self._plan_url(id_cat=item["id_cat"], id_reg=item["id_reg"]))
                    detail = self._parse_detail(html)
                    detail_budget -= 1
                except urllib.error.URLError:
                    pass

            if detail.get("titulo"):
                titulo = detail["titulo"]
            if detail.get("fecha"):
                fecha = detail["fecha"]
            exp_ref = (
                detail.get("expediente_urbanisme")
                or detail.get("expediente_ajuntament")
                or f"idReg-{item['id_reg']}"
            )
            key = f"{item['id_cat']}-{item['id_reg']}-{exp_ref}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo, categoria),
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "liferay_planejament",
                "categoria_planejament": categoria,
                "id_reg": item["id_reg"],
                "id_cat": item["id_cat"],
            }
            if detail.get("expediente_ajuntament"):
                rec["expediente_ajuntament"] = detail["expediente_ajuntament"]
            if detail.get("expediente_urbanisme"):
                rec["expediente_urbanisme"] = detail["expediente_urbanisme"]
            if detail.get("geometry_source_url"):
                rec["visor_url"] = detail["geometry_source_url"]
            self._attach_geometry(rec, detail)
            rows.append(rec)
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TRAMITES_URBANISMO_URL)
        except urllib.error.URLError:
            return rows
        for m in RE_TRAMITE_LINK.finditer(html):
            path, titulo = m.group(1), _strip_html(m.group(2))
            url = f"{self.seu_base}{path}" if path.startswith("/") else path
            titulo_l = titulo.lower()
            if not any(
                k in titulo_l
                for k in ("comunicaci", "licenc", "obra", "edificaci", "instalaci", "reforma")
            ):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "comunicación previa / licencia obra"
                    if "comunicaci" in titulo_l
                    else "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "seu_tramite",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", TRAMITES_URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "índice trámites obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de obras — urbanismo Girona",
                "url": TRAMITES_URBANISMO_URL,
                "source": "ayuntamiento",
                "origen": "seu_tramite",
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
        rows = self._collect_tramites_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": len(rows),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
        rows = self._collect_planejament()
        if not rows:
            rows = [
                {
                    "id": _stable_id("proy", self._plan_url()),
                    "municipio": MUNICIPIO,
                    "titulo": "Planejament i gestió urbanística vigent — índice PGOU",
                    "fecha": None,
                    "tipo": "PGOU",
                    "url": self._plan_url(),
                    "source": "ayuntamiento",
                    "origen": "liferay_planejament",
                }
            ]
        rows.append(
            {
                "id": _stable_id("proy", UMAT_VISOR),
                "municipio": MUNICIPIO,
                "titulo": "Visor UMAT — planejament (actualitzat no normatiu)",
                "fecha": None,
                "tipo": "visor GIS",
                "url": UMAT_VISOR,
                "source": "ayuntamiento",
                "origen": "visor",
            }
        )
        rows.append(
            {
                "id": _stable_id("proy", EXPOSICION_URL),
                "municipio": MUNICIPIO,
                "titulo": "Expedientes a exposición pública — sede electrónica",
                "fecha": None,
                "tipo": "información pública",
                "url": EXPOSICION_URL,
                "source": "ayuntamiento",
                "origen": "seu_exposicio",
            }
        )
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if has_area_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "planejament": sum(1 for r in rows if r.get("origen") == "liferay_planejament"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
