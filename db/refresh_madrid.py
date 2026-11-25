"""Publish Madrid's refreshed SIGMA data and both current municipal CSVs."""

import argparse
import json
import logging

from db.ingest import sync_municipio_output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    report = sync_municipio_output("madrid", madrid_licenses="skip" if args.projects_only else "current")
    if report["status"] != "ok":
        raise RuntimeError(report.get("reason", "La ingesta de Madrid no se completó"))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
