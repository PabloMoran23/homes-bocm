"""Normalización de resumenContenido del visor municipal (VSURB)."""

from __future__ import annotations

import re
from typing import Any


def normalize_resumen_contenido(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = re.sub(r"\s+", " ", value.strip())
    return s or None


def resumen_contenido_from_visor_ficha(ficha: Any) -> str | None:
    if not isinstance(ficha, dict):
        return None
    return normalize_resumen_contenido(ficha.get("resumenContenido"))
