from __future__ import annotations

from pathlib import Path
from typing import Any

from municipio.adapters.base import LicenciasAdapter


class NoneLicenciasAdapter(LicenciasAdapter):
    """Placeholder cuando el subagente aún no implementó fuente de licencias."""

    def backfill(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl.write_text("", encoding="utf-8")
        return {"rows": 0, "status": "none", "message": "Sin adapter de licencias"}

    def update(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return {"rows": 0, "status": "none", "message": "Sin adapter de licencias"}
