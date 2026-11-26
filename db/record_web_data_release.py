#!/usr/bin/env python3
"""Record a web data release (written by web/scripts/publish-web-data.mjs
--release-out) in homes.web_data_release.

The web never reads this table; it is the release log for monitoring.

Usage: python3 db/record_web_data_release.py web-data-release.json
"""
from __future__ import annotations

import json
import os
import sys

import psycopg2


def main(path: str) -> int:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("record_web_data_release: SUPABASE_DB_URL is required", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        r = json.load(fh)
    with psycopg2.connect(url, connect_timeout=15) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO homes.web_data_release
              (version, source, git_sha, run_id, file_count, changed_files, total_bytes, uploaded_bytes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (version) DO NOTHING
            """,
            (
                r["version"],
                r["source"],
                r.get("git_sha"),
                r.get("run_id"),
                r["file_count"],
                r["changed_files"],
                r["total_bytes"],
                r["uploaded_bytes"],
            ),
        )
    print(f"record_web_data_release: {r['version']} ({len(r['changed_files'])} changed files)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
