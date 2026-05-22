from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.registry import load_portal_adapter, resolve_portal_adapter_spec
from municipio.manifest import MunicipioManifest


def _out_path(manifest: MunicipioManifest) -> Path:
    return manifest.output_dir / "licencias.jsonl"


def _state_path(manifest: MunicipioManifest) -> Path:
    return manifest.output_dir / "licencias.state.json"


def _ensure_state(path: Path) -> Path:
    if not path.is_file():
        path.write_text("{}", encoding="utf-8")
    return path


def backfill(manifest: MunicipioManifest) -> dict[str, Any]:
    if not manifest.licencias.enabled:
        return {"skipped": True, "reason": "licencias.disabled"}
    manifest.ensure_output_dir()
    adapter = load_portal_adapter(manifest)
    out = _out_path(manifest)
    result = adapter.backfill_licencias(out)
    spec = resolve_portal_adapter_spec(manifest)
    state = {
        "last_backfill": datetime.now(timezone.utc).isoformat(),
        "adapter": spec,
        "source": "ayuntamiento",
        "portal_url": manifest.portal.base_url,
        "result": result,
    }
    _state_path(manifest).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**result, "path": str(out), "adapter": spec, "source": "ayuntamiento"}


def update(manifest: MunicipioManifest) -> dict[str, Any]:
    if not manifest.licencias.enabled:
        return {"skipped": True, "reason": "licencias.disabled"}
    manifest.ensure_output_dir()
    adapter = load_portal_adapter(manifest)
    out = _out_path(manifest)
    state_path = _ensure_state(_state_path(manifest))
    result = adapter.update_licencias(out, state_path)
    spec = resolve_portal_adapter_spec(manifest)
    return {**result, "path": str(out), "adapter": spec, "source": "ayuntamiento"}
