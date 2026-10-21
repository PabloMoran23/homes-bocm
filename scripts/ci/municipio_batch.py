#!/usr/bin/env python3
"""Bounded, isolated municipal backfills; publish and mark done only after validation."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def parse_slugs(value: str) -> list[str]:
    values = json.loads(value) if value.strip().startswith("[") else value.replace(",", " ").split()
    if not isinstance(values, list) or any(not isinstance(s, str) or not SLUG.fullmatch(s) or s == "_template" for s in values):
        raise ValueError("Expected municipal slugs, not paths or shell commands")
    return sorted(set(values))


def changed_slugs(base: str, head: str = "HEAD") -> list[str]:
    paths = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=ACMR", base, head], cwd=ROOT, text=True).splitlines()
    touched = set(paths)
    slugs = set()
    for manifest in (ROOT / "data/municipios").glob("*/manifest.yaml"):
        slug = manifest.parent.name
        if not SLUG.fullmatch(slug):
            continue
        adapter = re.search(r'^\s*adapter:\s*[\'\"]?([\w.]+)', manifest.read_text(), re.M)
        module = adapter.group(1).replace(".", "/") + ".py" if adapter else ""
        if str(manifest.relative_to(ROOT)) in touched or module in touched:
            slugs.add(slug)
    return sorted(slugs)


def assert_ready(report: dict) -> None:
    projects = report.get("datasets", {}).get("proyectos", {})
    if report.get("overall") not in {"ok", "partial"} or projects.get("rows", 0) < 1 or projects.get("with_coords", 0) < 1:
        raise ValueError("Insufficient project/coordinate coverage")
    if any(d.get("geography_quarantined", 0) for d in report.get("datasets", {}).values()):
        raise ValueError("Quarantined geography requires review")


def quarantine_snapshot(output: Path, slug: str, directory: Path) -> int:
    """Retain rejected source rows in the audit artifact, never in the sync input."""
    rejected = []
    for kind in ('proyectos', 'licencias'):
        path = output / f'{kind}.jsonl'
        if not path.exists():
            continue
        keep = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('geography_validation', {}).get('errors'):
                rejected.append({'dataset': kind, 'record': row})
            else:
                keep.append(line)
        path.write_text(''.join(line + '\n' for line in keep))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{slug}-quarantined.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rejected))
    return len(rejected)


def worker(slug: str, publish: bool) -> dict:
    sys.path.insert(0, str(ROOT))
    from municipio.manifest import load_manifest
    from municipio.orchestrator import run
    from municipio.sync_supabase import sync_manifest
    manifest = load_manifest(slug)
    # Backfill already obtains a complete snapshot. Do not scrape it a second time.
    for step in ("proyectos_backfill", "licencias_backfill", "enrich_geometry", "geocode"):
        result = run(manifest, step, staging=True)
        for name, value in result["steps"].items():
            if value.get("error") or value.get("status") in {"error", "deferred", "failed"}:
                raise RuntimeError(f"{name}: {value}")
    rejected = quarantine_snapshot(manifest.output_dir, slug, ROOT / "output/municipio-batch")
    run(manifest, "validate", staging=True)
    report = json.loads((manifest.output_dir / "parity-report.json").read_text())
    assert_ready(report)
    records = [json.loads(line) for line in (manifest.output_dir / "proyectos.jsonl").read_text().splitlines() if line.strip()]
    if any("municipio_centroid" in str(row.get("coord_source", "")) for row in records):
        raise ValueError("Municipality-centre placeholders are not project coordinates")
    if publish and not (os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")):
        raise ValueError("Publication requires database credentials")
    synced = sync_manifest(manifest, dry_run=not publish)
    if synced.get("status") != ("ok" if publish else "dry_run"):
        raise RuntimeError(f"Sync failed: {synced}")
    return {"slug": slug, "status": "ok", "published": publish, "parity": report, "sync": synced, "quarantined": rejected}


def run_one(slug: str, publish: bool, timeout: int, directory: Path) -> dict:
    command = [sys.executable, str(Path(__file__).resolve()), "worker", slug]
    if publish:
        command.append("--publish")
    path = directory / f"{slug}.json"
    path.unlink(missing_ok=True)
    try:
        with (directory / f"{slug}.log").open("w") as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        if process.returncode or not path.exists():
            lines = (directory / f"{slug}.log").read_text().strip().splitlines()
            reason = lines[-1][-400:] if lines else f"worker exit {process.returncode}"
            return {"slug": slug, "status": "failed", "reason": reason}
        return json.loads(path.read_text())
    except subprocess.TimeoutExpired:
        return {"slug": slug, "status": "failed", "reason": f"timeout after {timeout}s"}


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    detect = sub.add_parser("detect")
    detect.add_argument("--base", required=True)
    detect.add_argument("--head", default="HEAD")
    for command in ("run", "worker"):
        p = sub.add_parser(command)
        p.add_argument("slugs")
        p.add_argument("--publish", action="store_true")
        if command == "run":
            p.add_argument("--workers", type=int, default=4)
            p.add_argument("--timeout", type=int, default=600)
            p.add_argument("--pr-url", default="")
    args = parser.parse_args()
    if args.command == "detect":
        print(json.dumps(changed_slugs(args.base, args.head)))
        return 0
    slugs = parse_slugs(args.slugs)
    directory = ROOT / "output/municipio-batch"
    directory.mkdir(parents=True, exist_ok=True)
    if args.command == "worker":
        if len(slugs) != 1:
            parser.error("worker requires exactly one slug")
        result = worker(slugs[0], args.publish)
        (directory / f"{slugs[0]}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not 1 <= args.workers <= 8 or args.timeout < 1:
        parser.error("workers must be 1..8 and timeout positive")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(run_one, s, args.publish, args.timeout, directory): s for s in slugs}
        for future in as_completed(pending):
            result = future.result()
            if args.publish and result["status"] == "ok":
                # Only this parent writes queue.yaml: workers never mutate the queue.
                command = [sys.executable, "-m", "municipio", "queue", "done", "--municipio", result["slug"], "--notes", f"Validated batch publication; {result.get('quarantined', 0)} geography records quarantined; run {os.environ.get('GITHUB_RUN_ID', 'local')}"]
                if args.pr_url:
                    command.extend(["--pr-url", args.pr_url])
                proc = subprocess.run(command, cwd=ROOT)
                if proc.returncode:
                    result = {**result, "status": "failed", "reason": "queue update failed after publication"}
            results.append(result)
            print(json.dumps({k: v for k, v in result.items() if k not in {"parity", "sync"}}, ensure_ascii=False), flush=True)
    summary = {"results": sorted(results, key=lambda r: r["slug"])}
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(any(r["status"] != "ok" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
