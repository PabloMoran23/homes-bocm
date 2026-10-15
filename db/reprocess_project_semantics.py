#!/usr/bin/env python3
"""Replay the municipal contract in bounded, atomic, restartable batches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psycopg2
from ingest import pg_url, save_semantic_versions
from project_semantics import CONTRACT_VERSION, TEMPLATE_VERSION, apply, source_hash, source_record
from psycopg2.extras import Json, RealDictCursor, execute_values


def replay_batch(conn, *, after_id: str | None = None, batch_size: int = 100) -> dict:
    """Caller owns the transaction. History and canonical updates are atomic."""
    if not 1 <= batch_size <= 1000:
        raise ValueError('batch_size must be between 1 and 1000')
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT id, raw_features_json FROM homes.proyecto
                       WHERE municipio_slug IS NOT NULL
                         AND COALESCE(fuente, '') NOT IN ('sigma', 'bocm', 'bocm_legacy')
                         AND (%s::text IS NULL OR id > %s::text)
                       ORDER BY id LIMIT %s FOR UPDATE""", (after_id, after_id, batch_size))
        records = cur.fetchall()
    counts = {'examined': len(records), 'reprocessed': 0, 'discovered': 0,
              'last_id': records[-1]['id'] if records else after_id}
    changed = []
    for record in records:
        raw = record['raw_features_json']
        if not isinstance(raw, dict):
            raise ValueError(f"{record['id']}: missing original municipal record")
        previous = raw.get('_semantic_contract')
        previous = previous if isinstance(previous, dict) else {}
        source = source_record(raw)
        if (previous.get('source_hash') == source_hash(source)
                and previous.get('contract_version') == CONTRACT_VERSION
                and previous.get('template_version') == TEMPLATE_VERSION):
            continue
        row = {'id': record['id']}
        derived = apply(source, row)
        row['raw_features_json'] = Json({**source, '_semantic_contract': derived})
        changed.append(row)
        counts['reprocessed'] += 1
        counts['discovered'] += derived['status'] == 'discovered'
    if changed:
        with conn.cursor() as cur:
            # One history insertion and canonical update per batch, not per row.
            save_semantic_versions(cur, changed)
            values = [(r['id'], r['fase'], r['fase_normalizada'], r['fecha_aprob'],
                       r['bocm_pub_date'], r['resumen_contenido'], r['bocm_resumen'],
                       r['raw_features_json']) for r in changed]
            execute_values(cur, """UPDATE homes.proyecto AS p SET fase=v.fase,
                fase_normalizada=v.fase_normalizada, fecha_aprob=v.fecha_aprob::date,
                bocm_pub_date=v.bocm_pub_date::date, resumen_contenido=v.resumen_contenido,
                bocm_resumen=v.bocm_resumen, raw_features_json=v.raw_features_json::jsonb,
                updated_at=now() FROM (VALUES %s) AS v(id,fase,fase_normalizada,
                fecha_aprob,bocm_pub_date,resumen_contenido,bocm_resumen,raw_features_json)
                WHERE p.id=v.id::text""", values, page_size=batch_size)
    return counts


def replay(conn) -> dict[str, int]:
    """Compatibility entry point: preserve caller-owned transaction semantics."""
    total = {'examined': 0, 'reprocessed': 0, 'discovered': 0}
    after = None
    while True:
        result = replay_batch(conn, after_id=after)
        for key in total:
            total[key] += result[key]
        if result['examined'] < 100:
            return total
        after = result['last_id']


def connect_replay():
    return psycopg2.connect(pg_url(), connect_timeout=15, application_name='homes-semantic-replay')


def run_replay(*, batch_size=100, max_batches=None, connect_factory=None, progress=None):
    """Commit each batch independently; retries skip already-current versions.

    A connection failure rolls back only its current batch. No activation occurs.
    """
    if not 1 <= batch_size <= 1000 or (max_batches is not None and max_batches < 1):
        raise ValueError('Invalid batch limits')
    factory = connect_factory or connect_replay
    total = {'examined': 0, 'reprocessed': 0, 'discovered': 0, 'batches': 0, 'complete': False}
    after = None
    while max_batches is None or total['batches'] < max_batches:
        started = time.monotonic()
        conn = factory()
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='90s'; SET LOCAL idle_in_transaction_session_timeout='90s'")
            result = replay_batch(conn, after_id=after, batch_size=batch_size)
            conn.commit()
        except Exception:
            # A dead SSL connection cannot roll back; preserve the original
            # failure rather than masking it with InterfaceError on cleanup.
            if not conn.closed:
                try:
                    conn.rollback()
                except psycopg2.Error:
                    pass
            raise
        finally:
            conn.close()
        for key in ('examined', 'reprocessed', 'discovered'):
            total[key] += result[key]
        total['batches'] += 1
        after = result['last_id']
        total['complete'] = result['examined'] < batch_size
        if progress:
            progress({**total, 'batch_seconds': round(time.monotonic()-started, 3)})
        if total['complete']:
            break
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-batches', type=int, help='Bounded validation; output complete=false if more rows remain')
    args = parser.parse_args()
    progress = lambda item: print(json.dumps({'event': 'semantic_replay_batch', **item}), flush=True)
    result = run_replay(batch_size=args.batch_size, max_batches=args.max_batches, progress=progress)
    print(json.dumps({'event': 'semantic_replay_finished', **result}), flush=True)


if __name__ == '__main__':
    main()
