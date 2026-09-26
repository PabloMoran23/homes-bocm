"""Alias BOCM «Lozo-yuela» → municipio INE Lozoyuela-Navas-Sieteiglesias."""

from __future__ import annotations

from municipio.adapters.lozoyuela_navas_sieteiglesias import (
    LozoyuelaNavasSieteiglesiasAyuntamientoAdapter,
)

__all__ = ["LozoYuelaAyuntamientoAdapter"]


class LozoYuelaAyuntamientoAdapter(LozoyuelaNavasSieteiglesiasAyuntamientoAdapter):
    """Mismo portal que lozoyuela-navas-sieteiglesias; slug de cola para alias BOCM."""
