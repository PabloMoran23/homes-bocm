"""Publish Madrid's refreshed SIGMA data and both current municipal CSVs."""

import argparse
import json
import logging
from contextlib import closing

from db.ingest import connect, sync_municipio_output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with closing(connect()) as conn, conn:
        report = sync_municipio_output("madrid", conn=conn, madrid_licenses="skip" if args.projects_only else "current")
        if report["status"] != "ok":
            raise RuntimeError(report.get("reason", "La ingesta de Madrid no se completó"))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
