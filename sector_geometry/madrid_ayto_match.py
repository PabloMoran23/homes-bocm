"""
Cruce BOCM ↔ SIGMA (Ayto. Madrid capital).

Estrategia validada por madrid_ayto_match_eval:
  1. Solo match por número de expediente (normalizado).
  2. Sin fuzzy de denominación (generaba ~575 falsos positivos a score 0.72).
"""

from __future__ import annotations

import re
from typing import Any

EXP_SLASH_RE = re.compile(r"\b(\d{1,4}/\d{4}/\d{1,8})\b")
EXP_DASH_RE = re.compile(r"\b(\d{1,4})-(\d{4})-(\d{1,8})\b")


def _norm_exp(num: str) -> str:
    return re.sub(r"\s+", "", (num or "").strip())


def _exp_variants(num: str) -> list[str]:
    n = _norm_exp(num)
    if not n:
        return []
    out = {n}
    parts = n.split("/")
    if len(parts) == 3 and parts[2].isdigit():
        out.add(f"{parts[0]}/{parts[1]}/{parts[2].zfill(5)}")
        out.add(f"{parts[0]}/{parts[1]}/{parts[2].zfill(4)}")
        if parts[2].startswith("0"):
            out.add(f"{parts[0]}/{parts[1]}/{parts[2].lstrip('0') or '0'}")
    return list(out)


def expedientes_from_row(row: dict[str, str]) -> set[str]:
    """
    Extrae números de expediente SIGMA desde fila BOCM.
    Formatos: 711/2014/04512, 135-2023-02073, variantes zero-padded.
    """
    found: set[str] = set()

    def add_slash(num: str) -> None:
        for v in _exp_variants(num):
            found.add(v)

    pe = (row.get("procedimiento_expediente") or "").strip()
    if pe:
        if "/" in pe:
            add_slash(pe)
        else:
            m = EXP_DASH_RE.search(pe)
            if m:
                add_slash(f"{m.group(1)}/{m.group(2)}/{m.group(3)}")

    blob = " ".join(
        [
            row.get("procedimiento_expediente") or "",
            row.get("title") or "",
            row.get("resumen") or "",
            row.get("nombre_sector") or "",
            row.get("organo_aprobador") or "",
        ]
    )
    for m in EXP_SLASH_RE.finditer(blob):
        add_slash(m.group(1))
    for m in EXP_DASH_RE.finditer(blob):
        add_slash(f"{m.group(1)}/{m.group(2)}/{m.group(3)}")

    return found


def match_row(
    row: dict[str, str],
    by_exp: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, float | None]:
    """
    Devuelve (registro_sigma, match_type, score) o (None, None, None).
    Solo enlaza por expediente_numero presente en el índice SIGMA.
    """
    for e in expedientes_from_row(row):
        if e in by_exp:
            return by_exp[e], "expediente_numero", 1.0
    return None, None, None
