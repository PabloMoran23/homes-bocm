from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import psycopg2

from municipio.manifest import MunicipioManifest

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from ingest import sync_municipio_output  # noqa: E402


def park_manifest(manifest: MunicipioManifest, *, step: str, error: str) -> None:
    """El municipio agotó los reintentos. No vuelve al cron."""
    if not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return
    from ingest import park_dead_letter

    park_dead_letter(manifest.slug, step=step, error=error)


def sync_manifest(manifest: MunicipioManifest, *, dry_run: bool = False) -> dict[str, Any]:
    if not dry_run and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return {
            "status": "skipped",
            "reason": "sin SUPABASE_DB_URL",
            "slug": manifest.slug,
        }
    for attempt in range(1, 4):
        try:
            return sync_municipio_output(manifest.slug, dry_run=dry_run, manifest=manifest)
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as exc:
            code = exc.pgcode or ""
            transient = not code or code.startswith("08") or code in {"40001", "40P01", "55P03", "57P01"}
            if attempt == 3 or not transient:
                raise
            print(f"  {manifest.slug}: conexión o transacción de ingesta interrumpida, reintento {attempt + 1}/3", flush=True)
            time.sleep(2 ** attempt)
