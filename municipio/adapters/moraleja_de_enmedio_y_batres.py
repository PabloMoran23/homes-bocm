"""Portal compuesto BOCM: Moraleja de Enmedio + Batres (dos ayuntamientos)."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.batres import BatresAyuntamientoAdapter
from municipio.adapters.moraleja_de_enmedio import MoralejaDeEnmedioAyuntamientoAdapter
from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

SLUG = "moraleja-de-enmedio-y-batres"


class MoralejaDeEnmedioYBatresAyuntamientoAdapter(AyuntamientoAdapter):
    """Agrega sedes de Moraleja de Enmedio y Batres (slug compuesto en cola BOCM)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug or SLUG, config, base_url or "https://batres.sedelectronica.es")
        delay = float(self.config.get("request_delay_s", 0.35))
        ua = str(self.config.get("user_agent") or f"poc-bocm-{SLUG}/1.0")
        moraleja_cfg = dict(self.config.get("moraleja") or {})
        moraleja_cfg.setdefault("request_delay_s", delay)
        moraleja_cfg.setdefault("user_agent", ua)
        batres_cfg = dict(self.config.get("batres") or {})
        batres_cfg.setdefault("request_delay_s", delay)
        batres_cfg.setdefault("user_agent", ua)
        self._sources: list[AyuntamientoAdapter] = [
            MoralejaDeEnmedioAyuntamientoAdapter(
                "moraleja-de-enmedio",
                moraleja_cfg,
                "https://ayto-moraleja.sedelectronica.es",
            ),
            BatresAyuntamientoAdapter(
                SLUG,
                batres_cfg,
                "https://batres.sedelectronica.es",
            ),
        ]

    def _run_sources(self, method: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        stats: dict[str, Any] = {"status": "ok"}
        for src in self._sources:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                fn = getattr(src, method)
                result = fn(tmp_path)
                for line in tmp_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    merged[row["id"]] = row
                for key, val in result.items():
                    if key == "status":
                        continue
                    if isinstance(val, int):
                        stats[key] = int(stats.get(key, 0)) + val
                    else:
                        stats[key] = val
            finally:
                tmp_path.unlink(missing_ok=True)
        rows = list(merged.values())
        stats["rows"] = len(rows)
        return rows, stats

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
        rows, stats = self._run_sources("backfill_licencias")
        self._write_jsonl(out_jsonl, rows)
        return stats

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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
        rows, stats = self._run_sources("backfill_proyectos")
        self._write_jsonl(out_jsonl, rows)
        stats["with_geometry"] = sum(1 for r in rows if record_geometry(r))
        return stats

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
