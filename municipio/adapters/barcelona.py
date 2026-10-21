from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

PIU_PORTAL = "https://ajuntament.barcelona.cat/informaciourbanistica/cerca/es/"
PIU_SERVICE = (
    "https://ajuntament.barcelona.cat/informaciourbanistica/cerca/service"
)
SEDE_BASE = "https://seuelectronica.ajuntament.barcelona.cat"
MUNICIPIO = "Barcelona"
ID_PREFIX = "barcelona"

AP_LIST_KEYS = (
    "plans_ordenacio",
    "plans_usos",
    "globals",
    "alineacions_altres",
    "historics",
)

RE_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_iso_date(text: str | None) -> str | None:
    if not text:
        return None
    m = RE_ISO_DATE.match(str(text).strip())
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _proyecto_tipo(desc: str, section: str) -> str:
    n = (desc or "").lower()
    if section == "pu":
        return "proyecto urbanización"
    if section == "sp":
        return "sector pendiente planeamiento"
    if section == "ag":
        return "gestión urbanística"
    if "suspens" in n and "llic" in n:
        return "suspensión licencias"
    if "pla especial" in n or "pe " in n or "pe." in n:
        return "plan especial"
    if "pla de millora" in n or "pmu" in n or "pm " in n:
        return "plan de mejora urbana"
    if "modificaci" in n and ("pgm" in n or "pgou" in n or "general" in n):
        return "modificación planeamiento general"
    if "mperi" in n or "refosa" in n:
        return "revisión planeamiento"
    if "conveni" in n:
        return "convenio urbanístico"
    return "planeamiento"


def _transform_ring(ring: list[list[float]], transformer: Any) -> list[list[float]]:
    out: list[list[float]] = []
    for x, y in ring:
        lon, lat = transformer.transform(float(x), float(y))
        out.append([lon, lat])
    return out


def _geom_25831_to_wgs84(geom: dict[str, Any], transformer: Any) -> dict[str, Any] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return None
    if gtype == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [_transform_ring(ring, transformer) for ring in coords],
        }
    if gtype == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_transform_ring(ring, transformer) for ring in poly] for poly in coords
            ],
        }
    return None


class BarcelonaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal d'Informació Urbanística (PIU) — API JSON service/*."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PIU_PORTAL)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.user_agent = str(self.config.get("user_agent") or f"poc-bocm-{slug}/1.0")
        self.search_terms: list[str] = list(
            self.config.get("search_terms") or ["pla"]
        )
        self.geometry_limit = int(self.config.get("geometry_limit", 200))
        self.fetch_geometry = bool(self.config.get("fetch_geometry", True))
        self._transformer: Any | None = None

    def _transformer_25831(self) -> Any:
        if self._transformer is None:
            from pyproj import Transformer

            self._transformer = Transformer.from_crs(
                "EPSG:25831", "EPSG:4326", always_xy=True
            )
        return self._transformer

    def _fetch_json(self, url: str, *, timeout: int = 120) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            raise urllib.error.URLError(
                f"PIU error {err.get('code')}: {err.get('message')}"
            )
        return data if isinstance(data, dict) else {}

    def _service_url(self, path: str, *, query: dict[str, str] | None = None) -> str:
        base = f"{PIU_SERVICE}/{path.lstrip('/')}"
        q = {"format": "json"}
        if query:
            q.update(query)
        return f"{base}?{urllib.parse.urlencode(q)}"

    def _piu_item_url(self, clau1: str, clau2: str, clau3: str, tipus: str) -> str:
        claus = "/".join(
            urllib.parse.quote(p, safe="@*") for p in (clau1, clau2, clau3)
        )
        return f"{PIU_PORTAL}#/fitxa/{claus}/{tipus}/"

    def _fetch_geometry(
        self, clau1: str, clau2: str, clau3: str, tipus: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        c1 = urllib.parse.quote(clau1, safe="@*")
        path = f"GeometriaObjecteUrbanistic/{c1}/{clau2}/{clau3}/{tipus}"
        url = self._service_url(path)
        try:
            data = self._fetch_json(url, timeout=60)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None, None
        geoms = data.get("GEOM") or []
        if not geoms:
            return None, url
        merged: dict[str, Any] | None = None
        transformer = self._transformer_25831()
        for g in geoms:
            if not isinstance(g, dict):
                continue
            wgs = _geom_25831_to_wgs84(g, transformer)
            if not wgs:
                continue
            if merged is None:
                merged = wgs
            elif merged["type"] == "Polygon" and wgs["type"] == "Polygon":
                merged = {
                    "type": "MultiPolygon",
                    "coordinates": [merged["coordinates"], wgs["coordinates"]],
                }
            elif merged["type"] == "MultiPolygon" and wgs["type"] == "Polygon":
                merged["coordinates"].append(wgs["coordinates"])
            elif merged["type"] == "MultiPolygon" and wgs["type"] == "MultiPolygon":
                merged["coordinates"].extend(wgs["coordinates"])
        return merged, url

    def _load_darreres_meta(self) -> dict[str, dict[str, str]]:
        url = self._service_url("DarreresAprovacionsInicials")
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return {}
        out: dict[str, dict[str, str]] = {}
        for block_key in ("ap", "ag"):
            block = data.get(block_key) or {}
            for el in block.get("elements") or []:
                codi = str(el.get("c_codi") or el.get("c_clau1") or "").strip()
                if not codi:
                    continue
                out[codi] = {
                    "expedient": str(el.get("expedient") or "").strip(),
                    "fecha": _parse_iso_date(el.get("data_aprov_inicial"))
                    or _parse_iso_date(el.get("data_pub_ultim_tramit_bopb"))
                    or _parse_iso_date(el.get("data_pub_aprov_inicial_bopb"))
                    or _parse_iso_date(el.get("data_exp_criteris"))
                    or "",
                }
        return out

    def _iter_search_items(
        self, payload: dict[str, Any]
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """(section, geometry_tipus, element)."""
        items: list[tuple[str, str, dict[str, Any]]] = []
        seen: set[tuple[str, str, str, str]] = set()

        def add(section: str, tipus: str, el: dict[str, Any]) -> None:
            k = (
                section,
                str(el.get("c_clau1") or ""),
                str(el.get("c_clau2") or ""),
                str(el.get("c_clau3") or ""),
            )
            if k in seen:
                return
            seen.add(k)
            items.append((section, tipus, el))

        ap = payload.get("ap") or {}
        for key in AP_LIST_KEYS:
            for el in ap.get(key) or []:
                if isinstance(el, dict):
                    add("ap", "ap", el)

        for section, tipus in (("pu", "pu"), ("sp", "sp")):
            block = payload.get(section) or {}
            for el in block.get("elements") or []:
                if isinstance(el, dict):
                    add(section, tipus, el)

        ag = payload.get("ag") or {}
        for el in ag.get("elements") or []:
            if isinstance(el, dict):
                add("ag", "ag", el)

        return items

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        meta = self._load_darreres_meta()
        merged: dict[str, dict[str, Any]] = {}

        for term in self.search_terms:
            url = self._service_url(
                f"ServeiUnificatRecerca/{urllib.parse.quote(term)}"
            )
            try:
                payload = self._fetch_json(url, timeout=180)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for section, tipus, el in self._iter_search_items(payload):
                clau1 = str(el.get("c_clau1") or "").strip()
                clau2 = str(el.get("c_clau2") or "--").strip() or "--"
                clau3 = str(el.get("c_clau3") or "--").strip() or "--"
                codi = str(el.get("c_codi") or clau1).strip()
                desc = str(el.get("c_descripcio") or codi).strip()
                key = f"{section}|{clau1}|{clau2}|{clau3}"
                extra = meta.get(codi) or meta.get(clau1) or {}
                fecha = extra.get("fecha") or ""
                expediente = extra.get("expedient") or ""
                row = {
                    "clau1": clau1,
                    "clau2": clau2,
                    "clau3": clau3,
                    "tipus_geom": tipus,
                    "section": section,
                    "codi": codi,
                    "titulo": desc,
                    "fecha": fecha,
                    "expediente": expediente,
                    "tipo": _proyecto_tipo(desc, section),
                    "url": self._piu_item_url(clau1, clau2, clau3, tipus),
                }
                merged[key] = row

        rows = list(merged.values())
        rows.sort(key=lambda r: (r.get("fecha") or "", r.get("titulo") or ""), reverse=True)

        geom_budget = self.geometry_limit if self.fetch_geometry else 0
        for row in rows:
            if geom_budget <= 0:
                break
            g, geom_url = self._fetch_geometry(
                row["clau1"], row["clau2"], row["clau3"], row["tipus_geom"]
            )
            if g:
                row["geom_geojson"] = g
                row["geometry_crs"] = "EPSG:4326"
                row["geometry_source"] = "portal_piu_geometria"
                row["geometry_source_url"] = geom_url
                row["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(g)
                if cen:
                    row["lat"], row["lon"] = cen
                    row["coordinates_crs"] = "EPSG:4326"
                geom_budget -= 1

        out: list[dict[str, Any]] = []
        for row in rows:
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"{row['clau1']}|{row['clau2']}|{row['clau3']}|{row['section']}"),
                "municipio": MUNICIPIO,
                "titulo": row["titulo"],
                "fecha": row.get("fecha") or None,
                "tipo": row["tipo"],
                "url": row["url"],
                "source": "ayuntamiento",
                "expediente": row.get("expediente") or None,
                "codi_urbanistic": row.get("codi"),
            }
            if row.get("lat") is not None and row.get("lon") is not None:
                rec["lat"] = row["lat"]
                rec["lon"] = row["lon"]
                rec["coord_source"] = row.get("coord_source") or "portal_geometry_centroid"
            for k in (
                "geom_geojson",
                "geometry_crs",
                "geometry_source",
                "geometry_source_url",
                "coordinates_crs",
            ):
                if row.get(k):
                    rec[k] = row[k]
            out.append(rec)
        return out

    def _licencias_informativas(self) -> list[dict[str, Any]]:
        # El PIU permite consultar por parcela, pero no publica un listado
        # de concesiones. Las páginas de trámites no son licencias.
        return []

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {
            "rows": len(rows),
            "path": str(path),
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._licencias_informativas()
        return self._write_jsonl(out_jsonl, rows)

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        return self._write_jsonl(out_jsonl, rows)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
