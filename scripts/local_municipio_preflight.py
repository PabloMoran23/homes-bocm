#!/usr/bin/env python3
"""Read-only gate for a committed local batch before push or merge.

Does not create a PR, push, merge, run scrapers or contact a database.
Use the same [skip deploy] marker in the final GitHub merge subject.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from local_municipio_batches import allowed_paths, validate_manifest

MARKER = '[skip deploy]'
TOOLING = {
    'scripts/local_municipio_batches.py', 'scripts/local_municipio_preflight.py',
    'tests/test_local_municipio_batches.py', 'tests/test_local_municipio_preflight.py',
    'docs/local-municipio-batches.md',
}


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


def assert_workflows(repo):
    """Fail closed if an unfamiliar workflow can run on Git publication."""
    workflows = {}
    for path in (repo / '.github/workflows').glob('*'):
        if path.suffix not in {'.yml', '.yaml'}:
            continue
        data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        events = data.get('on', {})
        if isinstance(events, str):
            events = {events: {}}
        elif isinstance(events, list):
            events = {event: {} for event in events}
        # Independent schedules/manual runs are not caused by this batch.
        unsafe = set(events) - {'schedule', 'workflow_dispatch'}
        if unsafe:
            if path.name != 'check-vercel-build-filter.yml':
                raise ValueError(f'Unreviewed workflow trigger: {path.name}: {sorted(unsafe)}')
            for event in unsafe:
                cfg = events[event]
                expected = {
                    'web/scripts/vercel-should-build.sh',
                    'web/scripts/test-vercel-should-build.sh',
                    '.github/workflows/check-vercel-build-filter.yml',
                }
                if event not in {'push', 'pull_request'} or not isinstance(cfg, dict) or set(cfg.get('paths', [])) != expected:
                    raise ValueError(f'Build-filter workflow trigger changed: {event}')
        workflows[path.name] = sorted(events)
    return workflows


def assert_no_competing_pr(repo, slugs):
    branch = git(repo, 'branch', '--show-current')
    # The list is deliberately bounded; a full page is treated as incomplete.
    raw = subprocess.check_output(['gh', 'pr', 'list', '--repo', 'PabloMoran23/homes-bocm', '--state', 'open', '--limit', '1000', '--json', 'number,headRefName'], cwd=repo, text=True)
    prs = json.loads(raw)
    if len(prs) >= 1000:
        raise ValueError('Open PR inventory may be truncated')
    conflicts = []
    for pr in prs:
        if pr['headRefName'] == branch:
            continue
        raw = subprocess.check_output(['gh', 'api', '--paginate', f'repos/PabloMoran23/homes-bocm/pulls/{pr["number"]}/files', '--jq', '.[].filename'], cwd=repo, text=True)
        for path in raw.splitlines():
            parts = path.split('/')
            if len(parts) >= 4 and parts[:2] == ['data', 'municipios'] and parts[2] in slugs:
                conflicts.append((pr['number'], parts[2]))
            if path.startswith('municipio/adapters/') and Path(path).stem.replace('_', '-') in slugs:
                conflicts.append((pr['number'], Path(path).stem.replace('_', '-')))
    if conflicts:
        raise ValueError(f'Concurrent municipality PRs require reconciliation: {sorted(set(conflicts))}')
    return len(prs)


def inspect(repo, ledger_path, batch, base, deployment_audit):
    if git(repo, 'status', '--porcelain'):
        raise ValueError('Commit all reviewed work before preflight; checkout must be clean')
    head = git(repo, 'rev-parse', 'HEAD')
    if MARKER not in git(repo, 'log', '-1', '--format=%B'):
        raise ValueError('Published tip must contain [skip deploy]')
    # Remote inspection is read-only; do not trust a stale origin/main ref.
    remote = git(repo, 'ls-remote', 'origin', 'refs/heads/main').split()[0]
    if remote != git(repo, 'rev-parse', base):
        raise ValueError('Base is no longer current remote main; reconcile and review first')
    ledger = json.loads(ledger_path.read_text())
    if Path(ledger['repo']).resolve() != repo:
        raise ValueError('Ledger belongs to another checkout')
    rows = [row for row in ledger['municipios'] if row.get('batch') == batch and row['status'] == 'accepted']
    if len(rows) != 50 or len({r['ine_code'] for r in rows}) != 50 or len({r['slug'] for r in rows}) != 50:
        raise ValueError(f'Exactly 50 distinct accepted municipalities required; found {len(rows)}')
    expected = set().union(*(allowed_paths(row['slug']) for row in rows))
    permitted = expected | TOOLING | {
        f'{directory}/test_{r["slug"].replace("-", "_")}.py'
        for r in rows for directory in ('municipio', 'municipio/adapters')
    }
    changes = {}
    for line in git(repo, 'diff', '--name-status', '--no-renames', base, 'HEAD').splitlines():
        status, path = line.split('\t', 1)
        target = repo / path
        if not target.is_file() or any(part.is_symlink() for part in (target, *target.parents) if part != repo and repo in part.parents):
            raise ValueError(f'Batch output is not a regular file: {path}')
        if path == 'requirements-municipio.txt' and status == 'M':
            before = git(repo, 'show', f'{base}:requirements-municipio.txt').splitlines()
            after = (repo / path).read_text().splitlines()
            if after != before + ['requests>=2.32,<3', 'beautifulsoup4>=4.12,<5']:
                raise ValueError('Unexpected municipal dependency change')
            changes[path] = status
            continue
        if path not in permitted or status != 'A':
            raise ValueError(f'Unexpected batch change: {status} {path}')
        changes[path] = status
    if expected - changes.keys():
        raise ValueError(f'Missing municipal outputs: {sorted(expected - changes.keys())}')
    checked_prs = assert_no_competing_pr(repo, {r['slug'] for r in rows})
    evidence_hashes = {}
    for row in rows:
        validate_manifest(repo, row['slug'])
        path = Path(row.get('evidence', ''))
        if not path.is_file():
            raise ValueError(f'Missing review evidence for {row["slug"]}')
        report = json.loads(path.read_text())
        if report.get('slug') != row['slug'] or report.get('code_accepted') is not True:
            raise ValueError(f'Review did not accept code for {row["slug"]}')
        if report.get('static_ok') is not True or report.get('live_records', 0) < 1 or report.get('published') is not False:
            raise ValueError(f'Incomplete local validation for {row["slug"]}')
        hashes = report.get('files_sha256', {})
        for relative in allowed_paths(row['slug']):
            digest = hashlib.sha256((repo / relative).read_bytes()).hexdigest()
            if hashes.get(relative) != digest:
                raise ValueError(f'Code changed after review: {relative}')
        evidence_hashes[row['slug']] = hashlib.sha256(path.read_bytes()).hexdigest()
    workflows = assert_workflows(repo)
    config = json.loads((repo / 'web/vercel.json').read_text())
    if config.get('ignoreCommand') != 'bash scripts/vercel-should-build.sh':
        raise ValueError('Unexpected Vercel ignoreCommand')
    audit = json.loads(deployment_audit.read_text())
    checked = datetime.fromisoformat(audit['checked_at_utc'])
    age = (datetime.now(timezone.utc) - checked).total_seconds()
    if age < 0 or age >= 86400:
        raise ValueError('Refresh external deployment audit (maximum age 24 hours)')
    vercel = audit['vercel']
    if vercel.get('repository') != 'PabloMoran23/homes-bocm' or vercel.get('rootDirectory') != 'web' or vercel.get('effectiveRecentDeploymentSettings', {}).get('commandForIgnoringBuildStep') != 'bash scripts/vercel-should-build.sh':
        raise ValueError('Actual Vercel project has not been verified')
    if vercel.get('commandForIgnoringBuildStep') not in (None, 'bash scripts/vercel-should-build.sh') or vercel.get('otherProjectsLinkedToRepository') != 0 or vercel.get('deployHookCount') != 0 or audit['github'].get('repositoryHookCount') != 0:
        raise ValueError('External deployment configuration needs review')
    checks = {}
    for environment in ('preview', 'production'):
        env = {**os.environ, 'VERCEL_ENV': environment, 'VERCEL_GIT_COMMIT_SHA': head}
        proc = subprocess.run(['bash', 'web/scripts/vercel-should-build.sh'], cwd=repo, env=env, capture_output=True, text=True, timeout=45)
        if proc.returncode or 'skip (explicit [skip deploy] in commit)' not in proc.stdout:
            raise ValueError(f'Vercel {environment} would not explicitly skip: {proc.stdout} {proc.stderr}')
        checks[environment] = proc.stdout.strip()
    return {'ready': True, 'batch': batch, 'head': head, 'base': remote, 'municipalities': 50, 'open_prs_checked': checked_prs, 'changes': sorted(changes), 'evidence_sha256': evidence_hashes, 'workflows': workflows, 'vercel_checks': checks, 'required_merge_subject_marker': MARKER}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--deployment-audit', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.repo.resolve(), args.ledger, args.batch, args.base, args.deployment_audit), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Batch blocked: {error}')
