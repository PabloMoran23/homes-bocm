from __future__ import annotations

import importlib
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.manifest import MunicipioManifest


def _import_class(spec: str) -> type:
    module_path, _, class_name = spec.partition(":")
    if not module_path or not class_name:
        raise ValueError(f"Adapter inválido (usa modulo.clase:Clase): {spec!r}")
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def resolve_portal_adapter_spec(manifest: MunicipioManifest) -> str | None:
    """Adapter único del portal; fallback legacy en licencias.adapter."""
    if manifest.portal.adapter:
        return manifest.portal.adapter
    if manifest.licencias.adapter:
        return manifest.licencias.adapter
    return None


def load_portal_adapter(manifest: MunicipioManifest) -> AyuntamientoAdapter:
    spec = resolve_portal_adapter_spec(manifest)
    if not spec:
        raise ValueError(
            f"{manifest.slug}: falta portal.adapter en manifest.yaml — "
            "el subagente debe implementar el adapter del ayuntamiento."
        )
    cls = _import_class(spec)
    cfg = {**manifest.portal.config, **manifest.licencias.config}
    return cls(
        slug=manifest.slug,
        config=cfg,
        base_url=manifest.portal.base_url,
    )


def load_licencias_adapter(spec: str | None, slug: str, config: dict[str, Any]) -> Any:
    """Compatibilidad: carga clase legacy con backfill/update solo licencias."""
    if not spec:
        raise ValueError(f"{slug}: sin adapter de portal")
    cls = _import_class(spec)
    return cls(slug=slug, config=config)
