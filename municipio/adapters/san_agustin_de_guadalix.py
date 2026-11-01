"""Portal ayuntamiento San Agustín de Guadalix (variante BOCM «de» / mismo municipio que «del»)."""

from __future__ import annotations

from pathlib import Path
from municipio.onboarding_snapshot import reviewed_records

from typing import Any

from municipio.adapters.san_agustin_del_guadalix import SanAgustinDelGuadalixAyuntamientoAdapter

DE_ID_PREFIX = "san-agustin-de-guadalix"
DE_MUNICIPIO = "San Agustín de Guadalix"


class SanAgustinDeGuadalixAyuntamientoAdapter(SanAgustinDelGuadalixAyuntamientoAdapter):
    """Misma sede y transparencia que san-agustin-del-guadalix; IDs y slug BOCM distintos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        merged = dict(config or {})
        merged.setdefault("id_prefix", DE_ID_PREFIX)
        merged.setdefault("municipio_nombre", DE_MUNICIPIO)
        merged.setdefault("user_agent", "poc-bocm-san-agustin-de-guadalix/1.0")
        super().__init__(slug, merged, base_url)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        super()._write_jsonl(path, reviewed_records(path, rows))
