"""Replay exactly the ingestion/export territorial contract (dry run by default).

Optional evidence JSONL must contain records emitted by the Madrid XLSX downloader,
including their origin URL and adapter. Historical matching is exact on every original
field; a filename, key, coordinate or current derived marker is never evidence.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from license_territory import VERSION, resolve_territory
from sync_madrid_public_to_supabase import pg_url
from sector_geometry.madrid_licencias_download import LICENCIAS_RESOURCE_SLUG_BY_YEAR, _download_url_for_year


def original_fields(raw):
    return {k: v for k, v in raw.items() if k not in {
        '_territory', '_territorial_origin', 'source', 'fuente', 'municipio_slug'}}


def evidence_index(path):
    index = {}
    if path:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            origin = rec.get('_territorial_origin') or {}
            if (origin.get('adapter') != 'madrid-opendata'
                    or origin.get('url') not in {_download_url_for_year(y) for y in LICENCIAS_RESOURCE_SLUG_BY_YEAR}
                    or resolve_territory(rec)['municipioCode'] != '28079'):
                raise ValueError('Evidence must be re-extracted from the registered Madrid XLSX resources')
            index[json.dumps(original_fields(rec), sort_keys=True, ensure_ascii=False)] = origin
    return index


def replay_record(row, evidence):
    raw = dict(row.get('raw_json') or {})
    identity = json.dumps(original_fields(raw), sort_keys=True, ensure_ascii=False)
    if identity in evidence and not (raw.get('source') or raw.get('fuente') or row.get('fuente')):
        raw['_territorial_origin'] = evidence[identity]
    territory = resolve_territory({**row, 'raw_json': raw})
    raw['_territory'] = territory
    return territory, raw


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-jsonl')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    evidence = evidence_index(args.evidence_jsonl)
    counts = Counter()
    with psycopg2.connect(pg_url()) as con:
        if not args.apply:
            con.set_session(readonly=True)
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT id, municipio_slug, fuente, raw_json FROM homes.licencia ORDER BY id')
            for row in cur.fetchall():
                territory, raw = replay_record(row, evidence)
                counts[territory['reason'] or territory['municipio_slug']] += 1
                if row['municipio_slug'] == territory['municipio_slug'] and raw == row['raw_json']:
                    continue
                counts['changed'] += 1
                if args.apply:
                    cur.execute('UPDATE homes.licencia SET municipio_slug=%s, raw_json=%s, updated_at=now() WHERE id=%s',
                                (territory['municipio_slug'], Json(raw), row['id']))
    print(json.dumps({'policy': VERSION, 'mode': 'apply' if args.apply else 'dry-run', 'counts': counts}))

if __name__ == '__main__':
    main()
