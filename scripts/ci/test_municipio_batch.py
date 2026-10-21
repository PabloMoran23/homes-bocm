import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('municipio_batch', Path(__file__).with_name('municipio_batch.py'))
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class BatchTests(unittest.TestCase):
    def test_slug_input_and_deduplication(self):
        self.assertEqual(batch.parse_slugs('murcia,antas murcia'), ['antas', 'murcia'])
        self.assertEqual(batch.parse_slugs('["antas", "murcia"]'), ['antas', 'murcia'])
        for value in ['../antas', 'antas;echo', '["_template"]', '{}', '[1]']:
            with self.assertRaises(ValueError):
                batch.parse_slugs(value)

    def test_all_changed_manifests_and_adapter_only_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for slug in ('antas', 'murcia', 'untouched'):
                p = root / 'data/municipios' / slug / 'manifest.yaml'
                p.parent.mkdir(parents=True)
                p.write_text(f'portal:\n  adapter: municipio.adapters.{slug}:Adapter\n')
            paths = 'data/municipios/antas/manifest.yaml\nmunicipio/adapters/murcia.py\n'
            with patch.object(batch, 'ROOT', root), patch.object(batch.subprocess, 'check_output', return_value=paths):
                self.assertEqual(batch.changed_slugs('BASE'), ['antas', 'murcia'])

    def test_bad_coverage_and_quarantined_geography_block_publication(self):
        good = {'overall': 'partial', 'datasets': {'proyectos': {'rows': 2, 'with_coords': 1}}}
        batch.assert_ready(good)
        for bad in [{}, {**good, 'overall': 'none'}, {'overall': 'partial', 'datasets': {'proyectos': {'rows': 2, 'with_coords': 0}}}, {'overall': 'partial', 'datasets': {'proyectos': {'rows': 2, 'with_coords': 1, 'geography_quarantined': 1}}}]:
            with self.assertRaises(ValueError):
                batch.assert_ready(bad)

    def test_worker_timeout_isolated_and_stale_success_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'antas.json').write_text(json.dumps({'status': 'ok'}))
            with patch.object(batch.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 1)):
                self.assertEqual(batch.run_one('antas', False, 1, directory)['status'], 'failed')
            with patch.object(batch.subprocess, 'run', return_value=subprocess.CompletedProcess('worker', 1)):
                self.assertEqual(batch.run_one('antas', False, 1, directory)['status'], 'failed')

    def test_partial_batch_marks_only_successes_after_publication(self):
        def fake_worker(slug, publish, timeout, directory):
            return {'slug': slug, 'status': 'ok' if slug == 'antas' else 'failed', 'published': publish}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch, 'ROOT', Path(tmp)), patch.object(batch, 'run_one', side_effect=fake_worker), patch.object(batch.sys, 'argv', ['batch', 'run', 'antas murcia', '--publish']), patch.object(batch.subprocess, 'run', return_value=subprocess.CompletedProcess('queue', 0)) as queue:
                self.assertEqual(batch.main(), 1)
                self.assertEqual(queue.call_count, 1)
                self.assertIn('antas', queue.call_args.args[0])
                summary = json.loads((Path(tmp) / 'output/municipio-batch/summary.json').read_text())
                self.assertEqual(len(summary['results']), 2)

    def test_dry_run_never_marks_queue_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch, 'ROOT', Path(tmp)), patch.object(batch, 'run_one', return_value={'slug': 'antas', 'status': 'ok', 'published': False}), patch.object(batch.sys, 'argv', ['batch', 'run', 'antas']), patch.object(batch.subprocess, 'run') as queue:
                self.assertEqual(batch.main(), 0)
                queue.assert_not_called()

    def test_rejected_geography_saved_but_never_synced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'municipality'
            output.mkdir()
            good = {'id': 'good', 'geography_validation': {'errors': {}}}
            bad = {'id': 'outside', 'geography_validation': {'errors': {'geometry': 'outside_municipality_scope'}}}
            path = output / 'proyectos.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in (good, bad)) + '\n')
            count = batch.quarantine_snapshot(output, 'antas', root / 'audit')
            self.assertEqual(count, 1)
            self.assertEqual([json.loads(line)['id'] for line in path.read_text().splitlines()], ['good'])
            rejected = json.loads((root / 'audit/antas-quarantined.jsonl').read_text())
            self.assertEqual(rejected['record']['id'], 'outside')


if __name__ == '__main__':
    unittest.main()
