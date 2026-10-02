from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from municipio.adapters.olmeda_de_las_fuentes import OlmedaDeLasFuentesAyuntamientoAdapter

MUNICIPIO = "Olmedo de las Fuentes"
ID_PREFIX = "olmedo-de-las-fuentes"


def _remap_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Re-etiqueta filas del portal Olmeda de las Fuentes para el slug BOCM olmedo-de-las-fuentes."""
    out = dict(rec)
    out["municipio"] = MUNICIPIO
    old_id = str(out.get("id") or "")
    if old_id.startswith("olmeda-de-las-fuentes-"):
        out["id"] = old_id.replace("olmeda-de-las-fuentes-", f"{ID_PREFIX}-", 1)
    return out


class OlmedoDeLasFuentesAyuntamientoAdapter(OlmedaDeLasFuentesAyuntamientoAdapter):
    """
    Alias de cola: el CSV BOCM incluye «Olmedo de las Fuentes» (1 fila); municipio INE
    «Olmeda de las Fuentes» (olmedadelasfuentes.es). Mismo portal que olmeda-de-las-fuentes.
    """

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        remapped = [_remap_record(r) for r in rows]
        with path.open("w", encoding="utf-8") as f:
            for row in remapped:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
