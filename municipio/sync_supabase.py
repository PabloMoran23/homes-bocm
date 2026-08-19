from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from municipio.manifest import MunicipioManifest

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from ingest import sync_municipio_output  # noqa: E402


def sync_manifest(manifest: MunicipioManifest, *, dry_run: bool = False) -> dict[str, Any]:
    if not dry_run and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return {
            "status": "skipped",
            "reason": "sin SUPABASE_DB_URL",
            "slug": manifest.slug,
        }
    return sync_municipio_output(manifest.slug, dry_run=dry_run)
