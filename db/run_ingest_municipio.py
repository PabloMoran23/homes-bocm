#!/usr/bin/env python3
"""CLI de ingesta para el post-merge de municipios.

No forma parte de las PRs de adapters: cada scraper mergeado acaba en
`municipio run --step all`, y este script (o sync_municipio_output) vuelca
JSONL → homes.municipio / proyecto / licencia / documento / ingest_run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
POC_ROOT = DB_DIR.parent
sys.path.insert(0, str(DB_DIR))
sys.path.insert(0, str(POC_ROOT))

from ingest import sync_municipio_output  # noqa: E402


def main() -> int:
    slugs = sys.argv[1:]
    if not slugs:
        print("Uso: python3 db/run_ingest_municipio.py <slug> [slug...]", file=sys.stderr)
        return 2
    results = []
    rc = 0
    for slug in slugs:
        try:
            results.append(sync_municipio_output(slug))
        except Exception as e:
            results.append({"slug": slug, "status": "error", "error": str(e)})
            rc = 1
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if any(r.get("status") == "error" for r in results):
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
