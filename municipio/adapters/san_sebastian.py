"""Alias BOC Canarias «San Sebastián» (etiqueta San Sebastián/La Gomera) → INE 38036."""

from __future__ import annotations

from municipio.adapters.san_sebastian_de_la_gomera import (
    SanSebastianDeLaGomeraAyuntamientoAdapter,
)

__all__ = ["SanSebastianAyuntamientoAdapter"]


class SanSebastianAyuntamientoAdapter(SanSebastianDeLaGomeraAyuntamientoAdapter):
    """Mismo portal que san-sebastian-de-la-gomera; slug de cola para nombre abreviado en BOC."""
