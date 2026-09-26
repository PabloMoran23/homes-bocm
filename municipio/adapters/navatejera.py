from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from municipio.adapters.villaquilambre import VillaquilambreAyuntamientoAdapter

MUNICIPIO = "Navatejera"
ID_PREFIX = "navatejera"

RE_SUR_01 = re.compile(r"(?i)sur[-\s]?0?1")


def _remap_record(rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    out["municipio"] = MUNICIPIO
    out["pedania_de"] = "Villaquilambre"
    old_id = str(out.get("id") or "")
    if old_id.startswith("villaquilambre-"):
        out["id"] = old_id.replace("villaquilambre-", f"{ID_PREFIX}-", 1)
    return out


def _blob(rec: dict[str, Any]) -> str:
    return " ".join(
        str(rec.get(k) or "")
        for k in ("titulo", "url", "expte", "instrumento", "sector_code", "tipo", "nota")
    ).lower()


def _keep_proyecto(rec: dict[str, Any]) -> bool:
    blob = _blob(rec)
    if "navatejera" in blob:
        return True
    if RE_SUR_01.search(blob):
        return True
    if rec.get("origen") == "idecyl_wfs":
        titulo = str(rec.get("titulo") or "").upper()
        if "SUR" in titulo and "01" in titulo:
            return True
    return False


def _keep_licencia(rec: dict[str, Any]) -> bool:
    if rec.get("origen") == "wp_tramite":
        return True
    return "navatejera" in _blob(rec)


class NavatejeraAyuntamientoAdapter(VillaquilambreAyuntamientoAdapter):
    """
    Pedanía de Villaquilambre (León): sin ayuntamiento propio ni PlanPublica municipal.
    Reutiliza el portal de Villaquilambre filtrando actuaciones en Navatejera / SUR-01.
    """

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if "licencias" in path.name:
            kept = [_remap_record(r) for r in rows if _keep_licencia(r)]
        else:
            kept = [_remap_record(r) for r in rows if _keep_proyecto(r)]
        with path.open("w", encoding="utf-8") as f:
            for row in kept:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
