"""Benicarló (Castellón) — sedipualba tablón/RSS + ICV WFS (mismo portal que entrada compuesta)."""

from __future__ import annotations

from municipio.adapters.benicarlo_vinaros_benijofar import (
    BenicarloVinarosBenijofarAyuntamientoAdapter,
    TOWNS,
    TownConfig,
)


class BenicarloAyuntamientoAdapter(BenicarloVinarosBenijofarAyuntamientoAdapter):
    """Slug `benicarlo` → benicarlo.org + benicarlo.sedipualba.es (INE 12018)."""

    @property
    def towns(self) -> list[TownConfig]:
        return [TOWNS[0]]
