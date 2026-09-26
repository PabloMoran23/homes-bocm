from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from municipio.adapters.navalcarnero import NavalcarneroAyuntamientoAdapter

MUNICIPIO = "Navacarrenero"
ID_PREFIX = "navacarrenero"


def _remap_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Re-etiqueta filas del portal Navalcarnero para el slug BOCM navacarrenero."""
    out = dict(rec)
    out["municipio"] = MUNICIPIO
    old_id = str(out.get("id") or "")
    if old_id.startswith("navalcarnero-"):
        out["id"] = old_id.replace("navalcarnero-", f"{ID_PREFIX}-", 1)
    return out


class NavacarreneroAyuntamientoAdapter(NavalcarneroAyuntamientoAdapter):
    """
    Alias de cola: el CSV BOCM incluye «Navacarrenero» (1 fila) sin municipio INE propio.
    Portal y datos públicos son los de Navalcarnero (navalcarnero.es).
    """

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        remapped = [_remap_record(r) for r in rows]
        with path.open("w", encoding="utf-8") as f:
            for row in remapped:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
