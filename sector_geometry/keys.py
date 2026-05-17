from __future__ import annotations

import hashlib
import re
import unicodedata


_WS = re.compile(r"\s+")


def norm_text(s: str | None) -> str:
    if not s:
        return ""
    t = unicodedata.normalize("NFC", str(s).strip().lower())
    t = _WS.sub(" ", t)
    return t


def stable_sector_key(
    *,
    municipio: str | None,
    nombre_sector: str | None,
    municipio_provincia: str | None = None,
    boletin_source_id: str | None = None,
) -> str:
    """
    Clave estable (hex) para deduplicar filas CSV en un mismo ámbito territorial.
    Incluye fuente de boletín para no mezclar homónimos entre CCAA.
    """
    parts = [
        norm_text(boletin_source_id),
        norm_text(municipio),
        norm_text(nombre_sector),
        norm_text(municipio_provincia),
    ]
    blob = "||".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
