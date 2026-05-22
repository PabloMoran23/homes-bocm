from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AyuntamientoAdapter(ABC):
    """
    Contrato del subagente: extraer licencias y proyectos del portal municipal.
    Un módulo por municipio (scrape, API, datos abiertos del ayto.).
    """

    slug: str
    base_url: str

    def __init__(
        self,
        slug: str,
        config: dict[str, Any] | None = None,
        base_url: str = "",
    ):
        self.slug = slug
        self.config = config or {}
        self.base_url = base_url or str(self.config.get("base_url") or "")

    @abstractmethod
    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        """Histórico de licencias/urbanismo del ayuntamiento → licencias.jsonl."""

    @abstractmethod
    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        """Incremental licencias."""

    @abstractmethod
    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        """Expedientes/proyectos publicados en el portal → proyectos.jsonl."""

    @abstractmethod
    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        """Incremental proyectos del portal."""

    def describe(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "adapter": self.__class__.__name__,
            "base_url": self.base_url,
        }
