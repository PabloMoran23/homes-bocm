"""Replay geography from retained originals; dry-run is the default.

python -m municipio.geography_replay --slug leganes --slug san-sebastian-de-los-reyes --slug l-alfas-del-pi
Pass --apply to rewrite local derivatives. This command never writes to the DB.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from municipio.geography_control import RULE_VERSION, manifest_geography_config, normalize_record
from municipio.manifest import MUNICIPIOS_DIR, load_manifest


def replay_file(path: Path, *, cfg: dict, municipality: str, apply: bool = False, fetch_boundary: bool = True) -> dict:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    normalized = [normalize_record(r, cfg=cfg, municipality=municipality, fetch_boundary=fetch_boundary) for r in records]
    queue = [{"id": r.get("id") or r.get("licencia_key"), "input_hash": r["geography_validation"]["input_hash"],
              "errors": r["geography_validation"]["errors"], "rule_version": RULE_VERSION}
             for r in normalized if r["geography_validation"]["errors"]]
    changed = sum(a != b for a, b in zip(records, normalized))
    if apply:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in normalized))
        os.replace(tmp, path)
    return {"path": str(path), "rows": len(records), "changed": changed, "quarantined": len(queue), "replay_queue": queue}


def inspect_database(connection, *, slugs: list[str] | None = None) -> dict:
    """Read-only live control and replay queue; never executes UPDATE/INSERT."""
    from psycopg2.extras import RealDictCursor
    connection.set_session(readonly=True)
    result = {"rows": 0, "quarantined": 0, "needs_replay": 0, "replay_queue": []}
    queries = {
        "proyectos": "SELECT id::text AS id, municipio, municipio_slug, lat, lng, geom_geojson, raw_features_json AS source_original FROM homes.proyecto",
        "licencias": "SELECT licencia_key AS id, municipio_slug, lat, lng, raw_json AS source_original FROM homes.licencia",
    }
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        for dataset, sql in queries.items():
            if slugs:
                cursor.execute(sql + " WHERE municipio_slug = ANY(%s)", (slugs,))
            else:
                cursor.execute(sql)
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                for row in batch:
                    raw = row.pop("source_original") or {}
                    source = {**row, **raw} if isinstance(raw, dict) else dict(row)
                    slug = row.get("municipio_slug") or ""
                    try:
                        manifest = load_manifest(slug)
                        cfg = manifest_geography_config(manifest)
                        municipality = manifest.nombre
                    except FileNotFoundError:
                        cfg, municipality = {}, row.get("municipio") or ""
                    checked = normalize_record(source, cfg=cfg, municipality=municipality, fetch_boundary=True)
                    result["rows"] += 1
                    has_errors = bool(checked["geography_validation"]["errors"])
                    changed = any(checked.get(key) != row.get(key) for key in ("lat", "lng", "geom_geojson"))
                    if has_errors or changed:
                        result["quarantined"] += int(has_errors)
                        result["needs_replay"] += 1
                        result["replay_queue"].append({"dataset": dataset, "id": row["id"], "municipio_slug": slug,
                                                       "original": checked["geography_original"],
                                                       "validation": checked["geography_validation"],
                                                       "proposed_geography": {k: checked.get(k) for k in ("lat", "lng", "geom_geojson")},
                                                       "action": "recover_declared_source_and_replay" if has_errors else "publish_validated_replay"})
    connection.rollback()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", action="append")
    parser.add_argument("--input-root", type=Path, help="Alternative directory containing <slug>/{proyectos,licencias}.jsonl")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", action="store_true", help="Read-only live control and queue from original DB evidence")
    parser.add_argument("--report", type=Path, default=Path("geography-replay-report.json"))
    args = parser.parse_args()
    if args.database and args.apply:
        parser.error("--database is read-only and cannot be combined with --apply")
    slugs = args.slug or sorted(p.parent.name for p in MUNICIPIOS_DIR.glob("*/manifest.yaml"))
    report = {"rule_version": RULE_VERSION, "dry_run": not args.apply, "files": [], "errors": []}
    for slug in slugs:
        try:
            manifest = load_manifest(slug)
            cfg = manifest_geography_config(manifest)
            for name in ("proyectos.jsonl", "licencias.jsonl"):
                path = (args.input_root / slug / name) if args.input_root else manifest.output_dir / name
                if path.is_file():
                    report["files"].append(replay_file(path, cfg=cfg, municipality=manifest.nombre, apply=args.apply))
        except Exception as exc:
            report["errors"].append({"slug": slug, "error": str(exc)})
    if args.database:
        from db.ingest import connect
        try:
            with connect() as connection:
                report["database"] = inspect_database(connection, slugs=args.slug)
        except Exception as exc:
            report["errors"].append({"error": "database_control_failed", "detail": type(exc).__name__})
    if not report["files"] and not report.get("database"):
        report["errors"].append({"error": "original_datasets_unavailable", "slugs": slugs, "action": "Run source backfill before replay; a zero-file run cannot certify geography"})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"report": str(args.report), "files": len(report["files"]), "errors": len(report["errors"]),
                      "quarantined": sum(f["quarantined"] for f in report["files"])}))
    return 1 if report["errors"] or any(f["quarantined"] for f in report["files"]) or report.get("database", {}).get("needs_replay") else 0


if __name__ == "__main__":
    raise SystemExit(main())
