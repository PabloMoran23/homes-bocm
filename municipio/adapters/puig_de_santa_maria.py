"""Alias slug for El Puig de Santa Maria (same Dival sede + ICV WFS portal)."""

from pathlib import Path
from municipio.onboarding_snapshot import reviewed_records
from typing import Any

from municipio.adapters.el_puig_de_santa_maria import ElPuigDeSantaMariaAyuntamientoAdapter


class PuigDeSantaMariaAyuntamientoAdapter(ElPuigDeSantaMariaAyuntamientoAdapter):
    """Puig de Santa Maria — mismo ayuntamiento que `el-puig-de-santa-maria`."""

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        super()._write_jsonl(path, reviewed_records(path, rows))
