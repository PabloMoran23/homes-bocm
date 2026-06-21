from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from municipio.manifest import MunicipioManifest

POC_ROOT = Path(__file__).resolve().parents[1]


def _load_sync_fn():
    path = POC_ROOT / "db" / "sync_municipio_to_supabase.py"
    spec = importlib.util.spec_from_file_location("sync_municipio_to_supabase", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.sync_municipio


def sync_manifest(manifest: MunicipioManifest, *, dry_run: bool = False) -> dict[str, Any]:
    if not dry_run and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return {
            "status": "skipped",
            "reason": "sin SUPABASE_DB_URL",
            "slug": manifest.slug,
        }
    sync_fn = _load_sync_fn()
    return sync_fn(manifest.slug, dry_run=dry_run)
