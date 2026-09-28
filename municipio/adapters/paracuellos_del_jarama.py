"""Alias BOCM «Paracuellos del Jarama» → mismo portal que paracuellos-de-jarama."""

from __future__ import annotations

from municipio.adapters.paracuellos_de_jarama import ParacuellosDeJaramaAyuntamientoAdapter

__all__ = ["ParacuellosDelJaramaAyuntamientoAdapter"]


class ParacuellosDelJaramaAyuntamientoAdapter(ParacuellosDeJaramaAyuntamientoAdapter):
    """Slug de cola BOCM; lógica compartida con Paracuellos de Jarama."""
