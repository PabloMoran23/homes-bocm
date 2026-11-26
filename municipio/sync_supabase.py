from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg2

from municipio.manifest import MunicipioManifest

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = POC_ROOT / "db"
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

from ingest import sync_municipio_output  # noqa: E402


def retry_database_write(write: Callable[[], Any], *, slug: str, operation: str) -> Any:
    for attempt in range(1, 4):
        try:
            return write()
        except psycopg2.Error as exc:
            code = exc.pgcode or ""
            transient = isinstance(exc, psycopg2.errors.ReadOnlySqlTransaction) or code.startswith("08")
            transient = transient or code in {"40001", "40P01", "55P03", "57014", "57P01"}
            transient = transient or (
                not code and isinstance(exc, (psycopg2.InterfaceError, psycopg2.OperationalError))
            )
            if attempt == 3 or not transient:
                raise
            print(f"  {slug}: {operation} interrumpida ({code or type(exc).__name__}), "
                  f"reintento {attempt + 1}/3", flush=True)
            time.sleep(2 ** attempt)


def park_manifest(manifest: MunicipioManifest, *, step: str, error: str) -> None:
    """El municipio agotó los reintentos. No vuelve al cron."""
    if not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return
    from ingest import park_dead_letter

    retry_database_write(
        lambda: park_dead_letter(manifest.slug, step=step, error=error),
        slug=manifest.slug, operation="escritura de la cola de fallos",
    )


def sync_manifest(manifest: MunicipioManifest, *, dry_run: bool = False) -> dict[str, Any]:
    if not dry_run and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        return {
            "status": "skipped",
            "reason": "sin SUPABASE_DB_URL",
            "slug": manifest.slug,
        }
    result = retry_database_write(
        lambda: sync_municipio_output(manifest.slug, dry_run=dry_run, manifest=manifest),
        slug=manifest.slug, operation="ingesta",
    )
    result["anuncios"] = sync_anuncios(manifest, dry_run=dry_run)
    return result


def sync_anuncios(manifest: MunicipioManifest, *, dry_run: bool = False) -> dict[str, Any]:
    """Anuncios del tablón: aparte y sin aparcar el municipio si falla."""
    from anuncios import sync_municipio_anuncios

    try:
        return retry_database_write(
            lambda: sync_municipio_anuncios(manifest, dry_run=dry_run),
            slug=manifest.slug, operation="ingesta de anuncios",
        )
    except Exception as exc:  # noqa: BLE001 - auxiliar: proyectos y licencias ya están escritos
        print(f"  {manifest.slug}: anuncios no sincronizados ({exc})", flush=True)
        return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"[:500]}
