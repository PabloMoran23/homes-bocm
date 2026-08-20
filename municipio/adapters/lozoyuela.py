from __future__ import annotations

from typing import Any

from municipio.adapters.lozoyuela_navas_sieteiglesias import (
    LozoyuelaNavasSieteiglesiasAyuntamientoAdapter,
)


class LozoyuelaAyuntamientoAdapter(LozoyuelaNavasSieteiglesiasAyuntamientoAdapter):
    """Portal compartido con Lozoyuela-Navas-Sieteiglesias (fusión 2013); slug BOCM histórico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        cfg = dict(config or {})
        cfg.setdefault("municipio_name", "Lozoyuela")
        super().__init__(slug, cfg, base_url)
