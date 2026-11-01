from __future__ import annotations

import hashlib
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.geography_control import official_boundary
from municipio.geometry import record_geometry
from municipio.manifest import load_manifest

SOURCE_SLUGS = (
    "san-agustin-del-guadalix",
    "pedrezuela",
    "guadalix-de-la-sierra",
    "venturada",
    "cabanillas-de-la-sierra",
)

ID_PREFIX_TO_MUNICIPIO: dict[str, str] = {
    "san-agustin-del-guadalix": "San Agustín del Guadalix",
    "pedrezuela": "Pedrezuela",
    "guadalix-de-la-sierra": "Guadalix de la Sierra",
    "venturada": "Venturada",
    "cabanillas-de-la-sierra": "Cabanillas de la Sierra",
}

TOWN_CENTROIDS: dict[str, tuple[float, float]] = {
    "San Agustín del Guadalix": (40.6860, -3.6321),
    "Pedrezuela": (40.7451, -3.6030),
    "Guadalix de la Sierra": (40.7833, -3.6889),
    "Venturada": (40.8786, -3.5075),
    "Cabanillas de la Sierra": (40.8583, -3.7267),
}


def _jitter(lat: float, lng: float, key: str, *, spread_m: float = 180.0) -> tuple[float, float]:
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    angle = (h % 360) * math.pi / 180.0
    dist = ((h >> 8) % 1000) / 1000.0 * spread_m
    dlat = (dist * math.cos(angle)) / 111_320.0
    dlng = (dist * math.sin(angle)) / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lng + dlng


_BOUNDARY_CACHE: dict[str, dict[str, Any] | None] = {}


def _municipio_boundary(name: str) -> dict[str, Any] | None:
    key = name.strip()
    if not key:
        return None
    if key not in _BOUNDARY_CACHE:
        _BOUNDARY_CACHE[key] = official_boundary(key)
    return _BOUNDARY_CACHE[key]


def _infer_municipio_name(rec: dict[str, Any]) -> str:
    town = str(rec.get("municipio") or "").strip()
    if town:
        return town
    rid = str(rec.get("id") or "")
    for prefix, name in ID_PREFIX_TO_MUNICIPIO.items():
        if rid.startswith(f"{prefix}-"):
            return name
    return ""


def _attach_municipio_scope(rows: list[dict[str, Any]], *, manifest_nombre: str) -> None:
    """Map each row to IGN boundary of its town while keeping BOCM composite scope name."""
    for rec in rows:
        town = _infer_municipio_name(rec)
        if not town:
            continue
        rec.setdefault("municipio", town)
        rec["municipality_scope"] = [manifest_nombre]
        boundary = _municipio_boundary(town)
        if boundary:
            rec["municipal_boundaries"] = {manifest_nombre: boundary}


def _sanitize_inherited_coords(rows: list[dict[str, Any]]) -> None:
    """Member adapters may set lat/lon without coordinates_crs; drop so geocode can jitter."""
    for rec in rows:
        if record_geometry(rec):
            rec.setdefault("geometry_crs", "EPSG:4326")
            continue
        if rec.get("lat") is not None and not rec.get("coordinates_crs"):
            for k in ("lat", "lon", "lng", "coord_source", "centroid_lat", "centroid_lng"):
                rec.pop(k, None)


def _apply_town_centroids(rows: list[dict[str, Any]]) -> None:
    for rec in rows:
        if rec.get("lat") is not None:
            continue
        town = str(rec.get("municipio") or "")
        base = TOWN_CENTROIDS.get(town)
        if not base:
            continue
        rec_id = str(rec.get("id") or rec.get("url") or town)
        lat, lng = _jitter(base[0], base[1], rec_id)
        rec["lat"] = round(lat, 7)
        rec["lon"] = round(lng, 7)
        rec["lng"] = round(lng, 7)
        rec.setdefault("coord_source", "municipio_centroid_jitter")


class SanAgustinDelGuadalixPedrezuelaGuadalixDeLaSierraVenturadaYCabanillasDeLaSierraAyuntamientoAdapter(
    AyuntamientoAdapter,
):
    """Slug BOCM compuesto: agrega los cinco ayuntamientos del corredor norte (adaptadores existentes)."""

    def _source_adapters(self) -> list[AyuntamientoAdapter]:
        adapters: list[AyuntamientoAdapter] = []
        for slug in SOURCE_SLUGS:
            manifest = load_manifest(slug)
            adapters.append(load_portal_adapter(manifest))
        return adapters

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _merge_backfill(self, method: str, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources: dict[str, int] = {}

        for adapter in self._source_adapters():
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                getattr(adapter, method)(tmp_path)
                part = self._load_jsonl(tmp_path)
                sources[adapter.__class__.__name__] = len(part)
                for rec in part:
                    rid = str(rec.get("id") or "")
                    if rid and rid not in seen:
                        seen.add(rid)
                        rows.append(rec)
            finally:
                tmp_path.unlink(missing_ok=True)

        _sanitize_inherited_coords(rows)
        manifest_nombre = str(
            self.config.get("manifest_nombre")
            or "San Agustín del Guadalix, Pedrezuela, Guadalix de la Sierra, Venturada y Cabanillas de la Sierra"
        )
        _attach_municipio_scope(rows, manifest_nombre=manifest_nombre)
        _apply_town_centroids(rows)

        self._write_jsonl(out_jsonl, rows)
        stats: dict[str, Any] = {
            "rows": len(rows),
            "status": "ok",
            "sources": sources,
        }
        if method == "backfill_proyectos":
            stats["with_geometry"] = sum(1 for r in rows if record_geometry(r))
            stats["with_coords"] = sum(1 for r in rows if r.get("lat") is not None)
        return stats

    def _merge_update(
        self,
        method: str,
        out_jsonl: Path,
        state_path: Path,
    ) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self._merge_backfill(method.replace("update_", "backfill_"), out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "sources": stats.get("sources"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            **{k: v for k, v in stats.items() if k != "rows"},
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return self._merge_backfill("backfill_licencias", out_jsonl)

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self._merge_update("update_licencias", out_jsonl, state_path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        return self._merge_backfill("backfill_proyectos", out_jsonl)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self._merge_update("update_proyectos", out_jsonl, state_path)
