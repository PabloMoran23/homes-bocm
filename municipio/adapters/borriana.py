"""Borriana (ortografía valenciana) — mismo municipio y portal que Burriana."""

from __future__ import annotations

from municipio.adapters.burriana import BurrianaAyuntamientoAdapter


class BorrianaAyuntamientoAdapter(BurrianaAyuntamientoAdapter):
    """Alias slug `borriana` → portal burriana.es (Castellón, Comunitat Valenciana)."""
