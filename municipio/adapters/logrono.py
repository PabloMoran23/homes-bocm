from __future__ import annotations

import hashlib
import html
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
from municipio.geometry import geometry_centroid, has_area_geometry

BASE = "https://logrono.es"
EXPOSICION = f"{BASE}/exposicion-publica"
ULTIMAS_APROBACIONES = f"{BASE}/ultimas-aprobaciones"
WFS_BASE = "http://gis.logro-o.org/gs/geoserver/wfs"
MUNICIPIO = "Logroño"
ID_PREFIX = "logrono"

RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgm|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|urb\d|0712|unidad de ejecuci[oó]n)",
)
RE_SKIP = re.compile(
    r"(?i)(casta[nñ]as|subvencion|terrazas|convocatoria|adjudicaci[oó]n.*puestos|nota informativa)",
)
RE_UE_CODE = re.compile(
    r"(?i)\b(?:UE|U\.E\.|Unidad de Ejecuci[oó]n)\s*([NMQP]\d{2}\.\d+)|\b([NMQP]\d{2}\.\d+)\b",
)
RE_EXPEDIENTE = re.compile(
    r"(?i)\b(URB\d{2}[-_/]\d{4}[-_/]\d+|URB\d{2}_\d{4}_\d+|0712\s+\d{4}[/\-]\d+)",
)
RE_CALLE_NUM = re.compile(
    r"(?i)(?:calle|avenida|av\.?|ronda(?:\s+de)?|paseo|plaza|camino|carretera|"
    r"en\s+)([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\w\sÁÉÍÓÚÜÑáéíóúüñ\.\-']+?)"
    r"(?:\s+n[ºo°\.]?\s*(\d+))?",
)
RE_EN_CALLE = re.compile(
    r"(?i)\ben\s+(L[eé]rida|Moncalvillo|[^,;]+?)(?:\s+n[ºo°]?\s*(\d+))?",
)


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


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


class LogronoAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay exposición pública + últimas aprobaciones; geometría parcial vía GeoServer WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-logrono/1.0"))
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{BASE}{path if path.startswith('/') else '/' + path}"

    def _exposicion_page_url(self, cur: int, delta: int = 20) -> str:
        q = urllib.parse.urlencode(
            {
                "p_p_id": "es_logrono_exposicion_publica_ExposicionPublicaPortlet",
                "p_p_lifecycle": "0",
                "p_p_state": "normal",
                "p_p_mode": "view",
                "_es_logrono_exposicion_publica_ExposicionPublicaPortlet_mvcRenderCommandName": "/",
                "_es_logrono_exposicion_publica_ExposicionPublicaPortlet_resetCur": "false",
                "_es_logrono_exposicion_publica_ExposicionPublicaPortlet_cur": str(cur),
                "_es_logrono_exposicion_publica_ExposicionPublicaPortlet_delta": str(delta),
            }
        )
        return f"{EXPOSICION}?{q}"

    def _parse_exposicion(self, html_text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk in re.split(r'<h2 class="titulo">', html_text):
            m = re.match(r"([^<]+)</h2>(.*)", chunk, re.S)
            if not m:
                continue
            titulo = _strip_html(m.group(1))
            if titulo in {
                "REDES SOCIALES",
                "Dirección",
                "Teléfonos",
                "Contacto",
                "Horario",
                "Filtrar por",
            }:
                continue
            if RE_SKIP.search(titulo):
                continue
            body = m.group(2)
            dates = RE_FECHA_DMY.findall(body)
            fecha_inicio = None
            fecha_fin = None
            if dates:
                d, mo, y = dates[0]
                fecha_inicio = _parse_fecha_dmy(f"{d}/{mo}/{y}")
            if len(dates) > 1:
                d, mo, y = dates[1]
                fecha_fin = _parse_fecha_dmy(f"{d}/{mo}/{y}")
            doc_hrefs = re.findall(r'href="(/documents/[^"]+)"', body)
            url = self._abs(doc_hrefs[0]) if doc_hrefs else EXPOSICION
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "url": url,
                    "origen": "exposicion_publica",
                }
            )
        return rows

    def _collect_exposicion(self) -> list[dict[str, Any]]:
        seen_titles: set[str] = set()
        out: list[dict[str, Any]] = []
        delta = int(self.config.get("exposicion_delta", 20))
        max_pages = int(self.config.get("exposicion_max_pages", 30))
        for cur in range(1, max_pages + 1):
            try:
                page_rows = self._parse_exposicion(self._fetch(self._exposicion_page_url(cur, delta)))
            except urllib.error.URLError:
                break
            if not page_rows:
                break
            new = 0
            for row in page_rows:
                key = row["titulo"]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                out.append(row)
                new += 1
            if new == 0:
                break
        return out

    def _collect_ultimas_aprobaciones(self) -> list[dict[str, Any]]:
        try:
            html_text = self._fetch(ULTIMAS_APROBACIONES)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for raw in re.findall(r'<span class="">([^<]+)</span>', html_text):
            titulo = _strip_html(html.unescape(raw))
            if not titulo or RE_SKIP.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": ULTIMAS_APROBACIONES,
                    "origen": "ultimas_aprobaciones",
                }
            )
        return rows

    def _wfs_geojson(self, typename: str, cql: str, max_features: int = 3) -> dict[str, Any] | None:
        cache_key = f"{typename}|{cql}"
        if cache_key in self._geom_cache:
            cached = self._geom_cache[cache_key]
            return cached.get("geom") if cached else None

        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": typename,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "maxFeatures": str(max_features),
            "CQL_FILTER": cql,
        }
        url = f"{WFS_BASE}?{urllib.parse.urlencode(params)}"
        geom: dict[str, Any] | None = None
        source_url = url
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            feats = payload.get("features") or []
            if feats:
                geom = feats[0].get("geometry")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError):
            geom = None
        self._geom_cache[cache_key] = {"geom": geom, "url": source_url}
        return geom

    def _ue_codes(self, text: str) -> list[str]:
        seen: set[str] = set()
        codes: list[str] = []
        for m in RE_UE_CODE.finditer(text or ""):
            code = (m.group(1) or m.group(2) or "").upper()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        return codes

    def _address_hint(self, text: str) -> tuple[str | None, int | None]:
        m = RE_EN_CALLE.search(text or "")
        if m:
            vial = m.group(1).strip()
            num_s = m.group(2)
            if vial.lower().startswith("moncalvillo"):
                vial = "Moncalvillo"
            return vial, int(num_s) if num_s else None
        m = RE_CALLE_NUM.search(text or "")
        if m:
            vial = m.group(1).strip(" .")
            num_s = m.group(2)
            return vial, int(num_s) if num_s else None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        blob = rec.get("titulo") or ""
        for code in self._ue_codes(blob):
            geom = self._wfs_geojson("CARTO:Unidad de Ejecucion", f"titulo ILIKE '%{code}%'")
            if geom and geom.get("type") in {"Polygon", "MultiPolygon"}:
                rec["geom_geojson"] = geom
                rec["geometry_crs"] = "EPSG:4326"
                rec["geometry_source"] = "portal_wfs_ue"
                rec["geometry_source_url"] = self._geom_cache[f"CARTO:Unidad de Ejecucion|titulo ILIKE '%{code}%'"]["url"]
                rec["coord_source"] = "portal_geometry_centroid"
                rec["ue_code"] = code
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid
                return

        vial, numero = self._address_hint(blob)
        if not vial:
            return
        cql = f"vial ILIKE '%{vial}%'"
        if numero is not None:
            cql += f" AND numero={numero}"
        geom = self._wfs_geojson("CARTO:Portales", cql, max_features=1)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_wfs_portales"
        rec["geometry_source_url"] = self._geom_cache[f"CARTO:Portales|{cql}"]["url"]
        rec["coord_source"] = "portal_geometry_centroid"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _tipo_proyecto(self, blob: str) -> str:
        if re.search(r"(?i)convenio urban", blob):
            return "convenio"
        if re.search(r"(?i)estudio de detalle|urb27", blob):
            return "estudio de detalle"
        if re.search(r"(?i)modificaci[oó]n", blob):
            return "modificación planeamiento"
        if re.search(r"(?i)licencia", blob):
            return "licencia en exposición"
        if re.search(r"(?i)informaci[oó]n p[uú]blica|exposici[oó]n", blob):
            return "información pública"
        return "planeamiento"

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "exposicion_publica" and not RE_PROYECTO.search(blob):
            return None
        expte_m = RE_EXPEDIENTE.search(blob)
        key = (expte_m.group(1) if expte_m else None) or row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": self._tipo_proyecto(blob),
            "url": row.get("url") or EXPOSICION,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1).strip()
        if row.get("fecha_fin"):
            rec["fecha_fin"] = row["fecha_fin"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        expte_m = RE_EXPEDIENTE.search(blob)
        key = (expte_m.group(1) if expte_m else None) or row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia en exposición pública",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or EXPOSICION,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1).strip()
        self._attach_geometry(rec)
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_exposicion():
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_exposicion() + self._collect_ultimas_aprobaciones():
            rec = self._to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "exposicion_publica"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if has_area_geometry(r))
        with_coords = sum(1 for r in rows if r.get("lat") is not None and r.get("lon") is not None)
        return {
            "rows": len(rows),
            "status": "ok",
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion_publica"),
            "ultimas_aprobaciones": sum(1 for r in rows if r.get("origen") == "ultimas_aprobaciones"),
            "with_geometry": with_geom,
            "with_coords": with_coords,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
        result["added"] = max(0, after - before)
        return result
