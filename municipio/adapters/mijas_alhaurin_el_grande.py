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
from municipio.geometry import record_geometry
from municipio.manifest import load_manifest

SOURCE_SLUGS = ("mijas", "alhaurin-el-grande")

TOWN_CENTROIDS: dict[str, tuple[float, float]] = {
    "Mijas": (36.5957, -4.6375),
    "Alhaurín el Grande": (36.6430, -4.6914),
}


def _jitter(lat: float, lng: float, key: str, *, spread_m: float = 180.0) -> tuple[float, float]:
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    angle = (h % 360) * math.pi / 180.0
    dist = ((h >> 8) % 1000) / 1000.0 * spread_m
    dlat = (dist * math.cos(angle)) / 111_320.0
    dlng = (dist * math.sin(angle)) / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lng + dlng


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


class MijasAlhaurinElGrandeAyuntamientoAdapter(AyuntamientoAdapter):
    """Alias BOCM que agrega Mijas y Alhaurín el Grande (adaptadores existentes)."""

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
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        rows.append(rec)
            finally:
                tmp_path.unlink(missing_ok=True)

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
