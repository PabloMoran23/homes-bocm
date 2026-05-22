"""Normalización de direcciones del open data de Madrid (número con ceros a la izquierda)."""

from __future__ import annotations

import re
from typing import Any

_NUM_TOKEN_RE = re.compile(r"\b0+(\d+)\b")


def format_numero_via(raw: object) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        return None if n == 0 else str(n)
    return s


def normalize_direccion(raw: object) -> str | None:
    """Quita ceros a la izquierda de tokens numéricos en una dirección ya montada."""
    s = str(raw or "").strip()
    if not s:
        return None
    return _NUM_TOKEN_RE.sub(r"\1", s)


def build_direccion(row: dict[str, Any]) -> str | None:
    if row.get("direccion"):
        return normalize_direccion(row["direccion"])
    via = " ".join(
        p
        for p in [
            row.get("tipo_via"),
            row.get("nombre_via"),
            format_numero_via(row.get("nmero") or row.get("numero")),
        ]
        if p
    ).strip()
    return via or None
