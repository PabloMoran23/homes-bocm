#!/usr/bin/env python3
"""Local, flock-protected municipality assignments; never pushes, merges or deploys."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata
import yaml

BATCH_SIZE = 50
ACTIVE = {'assigned', 'review', 'accepted'}
PROVINCES = '''01:Araba,Álava,Araba/Álava
02:Albacete
03:Alicante,Alacant,Alicante/Alacant
04:Almería
05:Ávila
06:Badajoz
07:Balears,Illes Balears,Baleares,Balears Illes
08:Barcelona
09:Burgos
10:Cáceres
11:Cádiz
12:Castellón,Castelló,Castellón/Castelló
13:Ciudad Real
14:Córdoba
15:A Coruña,Coruña,Coruña A
16:Cuenca
17:Girona,Gerona
18:Granada
19:Guadalajara
20:Gipuzkoa,Guipúzcoa
21:Huelva
22:Huesca
23:Jaén
24:León
25:Lleida,Lérida
26:La Rioja,Rioja,Rioja La
27:Lugo
28:Madrid
29:Málaga
30:Murcia
31:Navarra
32:Ourense,Orense
33:Asturias
34:Palencia
35:Las Palmas,Palmas Las
36:Pontevedra
37:Salamanca
38:Santa Cruz de Tenerife
39:Cantabria
40:Segovia
41:Sevilla
42:Soria
43:Tarragona
44:Teruel
45:Toledo
46:Valencia,València,Valencia/València
47:Valladolid
48:Bizkaia,Vizcaya
49:Zamora
50:Zaragoza
51:Ceuta
52:Melilla'''


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower())


def names(value):
    result = set()
    for part in [str(value), *str(value).split('/')]:
        result.add(normalized(part))
        match = re.fullmatch(r'(.+),\s*(.+)', part)
        if match:
            result.add(normalized(match[2] + ' ' + match[1]))
        match = re.fullmatch(r'(.+)\s+\((El|La|Los|Las|L\x27|Es|Sa|Ses|Els|Les)\)', part, re.I)
        if match:
            result.add(normalized(match[2] + ' ' + match[1]))
    return result


PROVINCE_CODES = {normalized(alias): line.split(':')[0] for line in PROVINCES.splitlines() for alias in line.split(':')[1].split(',')}


def province(row):
    if row.get('province_code'):
        return str(row['province_code']).zfill(2)
    value = str(row.get('provincia', ''))
    return PROVINCE_CODES.get(normalized(value)) or PROVINCE_CODES.get(normalized(value.split('(')[-1].rstrip(')')))


def inventory(repo, queue, ine, open_prs=None):
    official = json.loads(Path(ine).read_text())
    index = defaultdict(set)
    for row in official:
        for alias in names(row['name']) | names(row.get('name_january', row['name'])):
            index[(str(row['province_code']).zfill(2), alias)].add(str(row['ine_code']).zfill(5))
    def identify(row):
        matches = set()
        for alias in names(row.get('nombre', row.get('name', ''))):
            matches.update(index.get((province(row), alias), set()))
        return next(iter(matches)) if len(matches) == 1 else None
    excluded_slugs, excluded_codes = set(), set()
    for path in (repo / 'data/municipios').glob('*/manifest.y*ml'):
        excluded_slugs.add(path.parent.name)
        row = yaml.safe_load(path.read_text()) or {}
        code = identify(row)
        if code:
            excluded_codes.add(code)
    if open_prs:
        prs = json.loads(Path(open_prs).read_text())
        for pr in prs:
            for entry in pr.get('files', []):
                path = entry['path'] if isinstance(entry, dict) else entry
                match = re.match(r'data/municipios/([^/]+)/', path)
                if match:
                    excluded_slugs.add(match[1])
                match = re.fullmatch(r'municipio/adapters/(.+)\.py', path)
                if match:
                    excluded_slugs.add(match[1].replace('_', '-'))
    rows = yaml.safe_load(Path(queue).read_text())['municipios']
    # Resolve all excluded slugs to INE identities before constructing candidates.
    for row in rows:
        if row['slug'] in excluded_slugs:
            code = identify(row)
            if code:
                excluded_codes.add(code)
    candidates, skipped, seen, seen_slugs = [], Counter(), set(), set()
    for row in rows:
        code = identify(row)
        slug = row['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            skipped['invalid_slug'] += 1
        elif row.get('status') != 'pending':
            skipped['queue_not_pending'] += 1
        elif slug in excluded_slugs or code in excluded_codes:
            skipped['existing_or_open_pr'] += 1
        elif not code:
            skipped['unresolved_identity'] += 1
        elif code in seen:
            skipped['duplicate_identity'] += 1
        elif slug in seen_slugs:
            skipped['duplicate_slug'] += 1
        else:
            candidates.append({'ine_code': code, 'slug': slug, 'nombre': row['nombre'], 'provincia': row.get('provincia'), 'status': 'pending'})
            seen.add(code)
            seen_slugs.add(slug)
    return candidates, dict(skipped)


@contextmanager
def locked_ledger(path, repo, apply=False):
    path = Path(path).expanduser().resolve()
    if path == repo or repo in path.parents or any((parent / '.git').exists() for parent in path.parents):
        raise ValueError('Ledger must be outside repository')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = json.loads(path.read_text()) if path.exists() else None
        box = [ledger]
        yield box
        if apply:
            fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.ledger-')
            try:
                with os.fdopen(fd, 'w') as handle:
                    json.dump(box[0], handle, indent=2, ensure_ascii=False)
                    handle.write('\n')
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)


def now():
    return datetime.now(timezone.utc).isoformat()


def reserve(ledger, batch, worker, count, slug=None):
    if count < 1:
        raise ValueError('count must be positive')
    current = [r for r in ledger['municipios'] if r.get('batch') == batch and r['status'] in ACTIVE]
    slots = BATCH_SIZE - len(current)
    selected = [r for r in ledger['municipios'] if r['status'] == 'pending' and (slug is None or r['slug'] == slug)][:min(count, max(0, slots))]
    if slug and not selected:
        raise ValueError('Requested slug unavailable or batch full')
    for row in selected:
        row.update(status='assigned', batch=batch, worker=worker, updated_at=now())
    return selected


def allowed_paths(slug):
    return {f'data/municipios/{slug}/manifest.yaml', f'data/municipios/{slug}/RESEARCH.md', f'municipio/adapters/{slug.replace("-", "_")}.py'}


def validate_changes(repo, base, slugs):
    allowed = set().union(*(allowed_paths(slug) for slug in slugs)) if slugs else set()
    result = subprocess.run(['git', 'diff', '--name-status', '--no-renames', base, '--'], cwd=repo, check=True, capture_output=True, text=True)
    changed = []
    for line in result.stdout.splitlines():
        status, path = line.split('\t', 1)
        if status != 'A' or path not in allowed:
            raise ValueError(f'Forbidden change: {status} {path}')
        changed.append(path)
    untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], cwd=repo, check=True, capture_output=True, text=True)
    for path in untracked.stdout.splitlines():
        if path not in allowed:
            raise ValueError(f'Forbidden untracked file: {path}')
        changed.append(path)
    for path in changed:
        target = repo / path
        if any(part.is_symlink() for part in [target, *target.parents] if part != repo and repo in part.parents) or not target.is_file():
            raise ValueError(f'Output is not regular file: {path}')
    for slug in slugs:
        missing = allowed_paths(slug) - set(changed)
        if missing:
            raise ValueError(f'Missing output files for {slug}: {sorted(missing)}')
    for slug in slugs:
        validate_manifest(repo, slug)
    return sorted(changed)


def validate_manifest(repo, slug):
    manifest = yaml.safe_load((repo / f'data/municipios/{slug}/manifest.yaml').read_text())
    if manifest.get('slug') != slug:
        raise ValueError(f'Manifest slug mismatch: {slug}')
    if manifest.get('schedule', {}).get('enabled') is not False:
        raise ValueError(f'schedule.enabled must explicitly be false: {slug}')
    if manifest.get('geocode', {}).get('jitter_missing') is not False:
        raise ValueError(f'geocode.jitter_missing must explicitly be false: {slug}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Persist changes; default is dry-run')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--queue', type=Path)
    init.add_argument('--ine', type=Path, required=True)
    init.add_argument('--open-prs', type=Path)
    commands.add_parser('status')
    claim = commands.add_parser('reserve')
    claim.add_argument('--batch', required=True)
    claim.add_argument('--worker', required=True)
    claim.add_argument('--count', type=int, default=1)
    claim.add_argument('--slug', help='Reserve this exact eligible slug')
    transition = commands.add_parser('set-status')
    transition.add_argument('--ine-code', required=True)
    transition.add_argument('--worker', required=True)
    transition.add_argument('--status', choices=['review', 'accepted', 'blocked'], required=True)
    transition.add_argument('--evidence', required=True, help='Review result/evidence path, or concrete blocking reason')
    release = commands.add_parser('release')
    release.add_argument('--ine-code', required=True)
    release.add_argument('--worker', required=True)
    release.add_argument('--reason', required=True)
    check = commands.add_parser('validate-batch')
    check.add_argument('--batch', required=True)
    check.add_argument('--base', required=True, help='Pinned integration baseline commit')
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    with locked_ledger(args.ledger, repo, args.apply) as box:
        ledger = box[0]
        if args.command == 'init':
            if ledger is not None:
                raise ValueError('Ledger already exists; resume with status/reserve, never reinitialize')
            rows, skipped = inventory(repo, args.queue or repo / 'data/municipios/queue.yaml', args.ine, args.open_prs)
            ledger = box[0] = {'version': 1, 'repo': str(repo), 'created_at': now(), 'batch_size': BATCH_SIZE, 'skipped': skipped, 'municipios': rows}
            output = {'candidates': len(rows), 'skipped': skipped}
        else:
            if ledger is None or ledger['repo'] != str(repo):
                raise ValueError('Missing ledger or repository mismatch')
            if args.command == 'status':
                output = {'counts': dict(Counter(r['status'] for r in ledger['municipios'])), 'batches': {b: dict(Counter(r['status'] for r in ledger['municipios'] if r.get('batch') == b)) for b in sorted({r['batch'] for r in ledger['municipios'] if r.get('batch')})}}
            elif args.command == 'reserve':
                output = reserve(ledger, args.batch, args.worker, args.count, args.slug)
            elif args.command == 'validate-batch':
                rows = [r for r in ledger['municipios'] if r.get('batch') == args.batch and r['status'] == 'accepted']
                if len(rows) != BATCH_SIZE:
                    raise ValueError(f'Batch requires exactly 50 accepted municipalities; found {len(rows)}')
                output = validate_changes(repo, args.base, [r['slug'] for r in rows])
            else:
                row = next(r for r in ledger['municipios'] if r['ine_code'] == args.ine_code)
                if row.get('worker') != args.worker:
                    raise ValueError('Worker does not own this reservation')
                if args.command == 'release':
                    if row['status'] not in {'assigned', 'review', 'blocked'}:
                        raise ValueError('Only assigned/review/blocked reservations may be explicitly released')
                    row.setdefault('history', []).append({**{k: row.get(k) for k in ('worker', 'batch', 'status')}, 'reason': args.reason, 'released_at': now()})
                    row.update(status='pending', worker=None, batch=None, updated_at=now())
                else:
                    valid = {'assigned': {'review', 'blocked'}, 'review': {'accepted', 'blocked'}}
                    if args.status not in valid.get(row['status'], set()):
                        raise ValueError('Invalid status transition')
                    if args.status == 'accepted':
                        validate_manifest(repo, row['slug'])
                    row.update(status=args.status, evidence=args.evidence, updated_at=now())
                output = row
        print(json.dumps({'dry_run': not args.apply, 'result': output}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, StopIteration) as error:
        raise SystemExit(str(error) or 'Municipality not found')
