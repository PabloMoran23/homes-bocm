"""Hourly bounded dispatcher. Queue state lives in PostgreSQL, never a CI cache."""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from municipio.manifest import POC_ROOT, list_manifest_slugs, load_manifest
from municipio.refresh_queue import Queue, REVIEW_SECONDS
from municipio.schedule import _schedule_config, _truthy


def review_config_hash(manifest):
    # Direct adapter plus shared rules. Changes requeue only the relevant source;
    # shared rule changes legitimately affect every source, still through budgets.
    from municipio.adapters.registry import resolve_portal_adapter_spec
    adapter = (resolve_portal_adapter_spec(manifest) or '').partition(':')[0]
    paths = [manifest.path, Path(__file__),
             POC_ROOT/'municipio/proyectos_runner.py', POC_ROOT/'municipio/licencias_runner.py',
             POC_ROOT/'municipio/adapters/portal.py', POC_ROOT/'municipio/adapters/registry.py']
    adapter_path = POC_ROOT / (adapter.replace('.','/')+'.py')
    if adapter_path.is_file():
        paths.append(adapter_path)
    digest = hashlib.sha256(b'review-contract-v1')
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def census():
    sources = []
    for slug in list_manifest_slugs():
        cfg = _schedule_config(slug)
        if slug == 'madrid' or not _truthy(cfg.get('enabled')):
            continue
        manifest = load_manifest(slug)
        interval = int(cfg.get('interval_days') or 15)
        if interval <= 0 or interval > 15:
            raise ValueError(f'{slug}: interval_days must be within the promised 15 days')
        sources.append({'slug':slug, 'host':urlparse(manifest.portal.base_url).hostname or slug,
                        'hash':review_config_hash(manifest),
                        'interval':interval*86400})
    return sources


def review(slug):
    """Source adapters must attest exhaustive review; legacy status=ok cannot do so.

    Restore the existing outputs when a source is partial, blocked or unverified.
    Only verified source outputs reach sync, which already uses stable identities.
    """
    from municipio import licencias_runner, proyectos_runner
    from municipio.orchestrator import run
    manifest = load_manifest(slug)
    output = manifest.output_dir
    with tempfile.TemporaryDirectory(prefix='review-') as tmp:
        backup = Path(tmp)/'output'
        existed = output.exists()
        if existed:
            shutil.copytree(output,backup)
        reviewed = False
        written = False
        enabled_count = 0
        try:
            for name, enabled, runner in (
                ('proyectos',manifest.proyectos.enabled,proyectos_runner.update),
                ('licencias',manifest.licencias.enabled,licencias_runner.update),
            ):
                if not enabled:
                    continue
                enabled_count += 1
                result = runner(manifest)
                if result.get('error') or result.get('review_complete') is not True:
                    raise RuntimeError(f'{name}: review_complete missing/false; source review unverified')
            if not enabled_count:
                raise RuntimeError('no enabled source to review')
            reviewed = True
            for step in ('enrich_geometry','geocode','sync_supabase','validate'):
                result = run(manifest,step)
                for payload in result['steps'].values():
                    if payload.get('error') or payload.get('status') in ('deferred','partial','failed') or (step == 'sync_supabase' and payload.get('status') == 'skipped'):
                        raise RuntimeError(f'{step}: {payload}')
                if step == 'sync_supabase':
                    written = True
            return {'complete':True,'written':True}
        except Exception as exc:
            if output.exists():
                shutil.rmtree(output)
            if existed:
                shutil.copytree(backup,output)
            return {'complete':False,'reviewed':reviewed,'written':written,'error':f'{type(exc).__name__}: {exc}'}


def _child(slug, result_path):
    try:
        result = review(slug)
    except Exception as exc:
        result = {'complete':False,'error':f'{type(exc).__name__}: {exc}'}
    Path(result_path).write_text(json.dumps(result))


def bounded_review(slug):
    # A hard bound is necessary: a runner timeout must leave a recoverable lease.
    # Child output is isolated; no IPC queue whose feeder thread could deadlock.
    with tempfile.TemporaryDirectory(prefix='review-result-') as tmp:
        result_path = str(Path(tmp)/'result.json')
        output = load_manifest(slug).output_dir
        backup = Path(tmp)/'prior-output'
        existed = output.exists()
        if existed:
            shutil.copytree(output,backup)
        child = multiprocessing.Process(target=_child,args=(slug,result_path))
        child.start()
        child.join(REVIEW_SECONDS)
        if child.is_alive():
            child.terminate()
            child.join(10)
            if child.is_alive():
                child.kill()
                child.join()
            if output.exists():
                shutil.rmtree(output)
            if existed:
                shutil.copytree(backup,output)
            return {'complete':False,'error':'review_timeout: SLA remains breached'}
        if not Path(result_path).exists():
            if output.exists():
                shutil.rmtree(output)
            if existed:
                shutil.copytree(backup,output)
            return {'complete':False,'error':f'review_worker_exit:{child.exitcode}'}
        return json.loads(Path(result_path).read_text())


def dispatch(queue, *, limit=3, worker=bounded_review, clock=time.time):
    out = []
    for _ in range(min(3,max(0,limit))):
        job = queue.claim(clock())
        if not job:
            break
        result = worker(job['slug'])
        accepted = queue.finish(job,clock(),**result)
        out.append({'slug':job['slug'],'lease_accepted':accepted,**result})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrics-only',action='store_true')
    parser.add_argument('--report',default='refresh-report.json')
    args = parser.parse_args()
    from ingest import connect
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SET search_path TO homes, public')
        conn.commit()
        queue = Queue(conn)
        if not args.metrics_only:
            queue.reconcile(census(),time.time())
        results = [] if args.metrics_only else dispatch(queue)
        observed_at = time.time()
        metrics = queue.metrics(observed_at)
        queue.checkpoint_metrics(observed_at,metrics)
        Path(args.report).write_text(json.dumps({'results':results,'metrics':metrics},indent=2))
        print(json.dumps(metrics,indent=2))
        if metrics['sla_violations'] or metrics['capacity_alarm'] or metrics['backlog_growth_alarm'] or any(not r.get('complete') for r in results):
            print('::error::Refresh SLA breached; see durable queue and refresh-report.json')
            return 1
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
