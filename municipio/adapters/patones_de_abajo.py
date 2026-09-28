from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from municipio.adapters.patones import PatonesAyuntamientoAdapter

MUNICIPIO = "Patones de Abajo"
ID_PREFIX = "patones-de-abajo"


def _remap_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Re-etiqueta filas del portal Patones para el slug BOCM patones-de-abajo."""
    out = dict(rec)
    out["municipio"] = MUNICIPIO
    old_id = str(out.get("id") or "")
    if old_id.startswith("patones-"):
        out["id"] = old_id.replace("patones-", f"{ID_PREFIX}-", 1)
    return out


class PatonesDeAbajoAyuntamientoAdapter(PatonesAyuntamientoAdapter):
    """
    Entidad local del municipio de Patones (sede en Patones de Abajo).
    Mismo portal WordPress + sede espublico que `patones`; slug BOCM separado (1 aviso).
    """

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        remapped = [_remap_record(r) for r in rows]
        with path.open("w", encoding="utf-8") as f:
            for row in remapped:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
