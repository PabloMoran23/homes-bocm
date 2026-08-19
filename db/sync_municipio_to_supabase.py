#!/usr/bin/env python3
"""
Sync datos del portal municipal (output/municipios/<slug>/) → Supabase homes.*.

Delega en db/ingest.sync_municipio_output (municipio, proyecto, licencia, documento, ingest_run).

Uso:
  python3 db/sync_municipio_to_supabase.py --municipio torrejon-de-ardoz
  python3 db/sync_municipio_to_supabase.py --all-done
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
POC_ROOT = DB_DIR.parent
sys.path.insert(0, str(DB_DIR))
sys.path.insert(0, str(POC_ROOT))

from ingest import sync_municipio_output  # noqa: E402
from municipio.manifest import list_manifest_slugs  # noqa: E402

# Retrocompat con código que importaba sync_municipio directamente.
sync_municipio = sync_municipio_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync portal municipal → Supabase")
    parser.add_argument("--municipio", "-m", action="append", dest="municipios")
    parser.add_argument("--all-done", action="store_true", help="Sync todos los manifests existentes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    slugs = args.municipios or []
    if args.all_done:
        slugs = list_manifest_slugs()
    if not slugs:
        parser.error("Indica --municipio <slug> o --all-done")

    results = []
    for slug in slugs:
        try:
            results.append(sync_municipio_output(slug, dry_run=args.dry_run))
        except Exception as e:
            results.append({"slug": slug, "status": "error", "error": str(e)})

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if all(r.get("status") in ("ok", "dry_run", "skipped") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
