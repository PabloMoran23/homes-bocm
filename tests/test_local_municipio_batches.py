"""No network, deployment, git mutations outside temporary test repositories."""
import importlib.util
import json
import multiprocessing
from pathlib import Path
import tempfile
import subprocess
import unittest
import yaml
import contextlib
import io

SPEC = importlib.util.spec_from_file_location('local_batches', Path(__file__).resolve().parents[1] / 'scripts/local_municipio_batches.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def concurrent_reserve(path, repo, worker):
    with m.locked_ledger(Path(path), Path(repo), True) as box:
        m.reserve(box[0], 'b1', worker, 30)


class BatchesTest(unittest.TestCase):
    def test_invalidate_accepted_retains_review_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root / 'repo'
            repo.mkdir()
            ledger = root / 'ledger.json'
            ledger.write_text(json.dumps({'repo': str(repo), 'municipios': [{
                'ine_code': '28001', 'slug': 'test', 'worker': 'one',
                'status': 'accepted', 'batch': 'a', 'evidence': 'review.json',
            }]}))
            with contextlib.redirect_stdout(io.StringIO()):
                m.main(['--repo', str(repo), '--ledger', str(ledger), '--apply',
                        'set-status', '--ine-code', '28001', '--worker', 'one',
                        '--status', 'blocked', '--evidence', 'concurrent-pr.json'])
            row = json.loads(ledger.read_text())['municipios'][0]
            self.assertEqual(row['status'], 'blocked')
            self.assertEqual(row['evidence'], 'concurrent-pr.json')
            self.assertEqual(row['history'][0]['evidence'], 'review.json')

    def test_cap_and_replacement(self):
        ledger = {'municipios': [{'ine_code': str(i), 'slug': str(i), 'status': 'pending'} for i in range(80)]}
        self.assertEqual(len(m.reserve(ledger, 'a', 'one', 35)), 35)
        self.assertEqual(len(m.reserve(ledger, 'a', 'two', 35)), 15)
        ledger['municipios'][0]['status'] = 'blocked'
        self.assertEqual(len(m.reserve(ledger, 'a', 'two', 35)), 1)
        self.assertEqual(len(m.reserve(ledger, 'a', 'three', 1)), 0)
        with self.assertRaises(ValueError):
            m.reserve(ledger, 'a', 'three', -1)

    def test_atomic_reservations(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root / 'repo'
            repo.mkdir()
            ledger = root / 'state.json'
            ledger.write_text(json.dumps({'municipios': [{'ine_code': str(i), 'status': 'pending'} for i in range(80)]}))
            processes = [multiprocessing.Process(target=concurrent_reserve, args=(str(ledger), str(repo), str(i))) for i in range(3)]
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            assigned = [r for r in json.loads(ledger.read_text())['municipios'] if r['status'] == 'assigned']
            self.assertEqual(len(assigned), 50)
            self.assertEqual(len({r['ine_code'] for r in assigned}), 50)

    def test_identity_and_exclusions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            existing = root / 'data/municipios/existing'
            existing.mkdir(parents=True)
            (existing / 'manifest.yaml').write_text('nombre: Other\nprovincia: Madrid\n')
            official = [{'ine_code': '28001', 'province_code': '28', 'name': 'Same'}, {'ine_code': '40001', 'province_code': '40', 'name': 'Same'}, {'ine_code': '28002', 'province_code': '28', 'name': 'Other'}, {'ine_code': '28003', 'province_code': '28', 'name': 'Open'}]
            ine = root / 'ine.json'
            ine.write_text(json.dumps(official))
            queue = root / 'queue.yaml'
            rows = [{'slug': slug, 'nombre': name, 'provincia': prov, 'status': 'pending'} for slug, name, prov in [('same', 'Same', 'Madrid'), ('same-segovia', 'Same', 'Segovia'), ('same-alias', 'Same', 'Madrid'), ('unknown', 'Same', 'Unknown'), ('other-alias', 'Other', 'Madrid'), ('open', 'Open', 'Madrid')]]
            queue.write_text(yaml.safe_dump({'municipios': rows}))
            prs = root / 'prs.json'
            prs.write_text(json.dumps([{'files': [{'path': 'data/municipios/open/RESEARCH.md'}]}]))
            candidates, skipped = m.inventory(root, queue, ine, prs)
            self.assertEqual([r['ine_code'] for r in candidates], ['28001', '40001'])
            self.assertEqual(skipped['duplicate_identity'], 1)
            self.assertEqual(skipped['unresolved_identity'], 1)
            self.assertEqual(skipped['existing_or_open_pr'], 2)

    def test_diff_guard_rejects_extra_and_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git('init')
            git('config', 'user.email', 'test@example.test')
            git('config', 'user.name', 'Test')
            (root / 'README').write_text('baseline')
            git('add', '.')
            git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            for path in m.allowed_paths('test'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('slug: test\nschedule:\n  enabled: false\ngeocode:\n  jitter_missing: false\n' if path.endswith('manifest.yaml') else '# evidence')
            self.assertEqual(len(m.validate_changes(root, base, ['test'])), 3)
            (root / 'web.txt').write_text('forbidden')
            with self.assertRaises(ValueError):
                m.validate_changes(root, base, ['test'])
            (root / 'web.txt').unlink()
            (root / 'README').write_text('modified')
            with self.assertRaises(ValueError):
                m.validate_changes(root, base, ['test'])

    def test_manifest_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'data/municipios/test/manifest.yaml'
            target.parent.mkdir(parents=True)
            target.write_text('slug: test\nschedule:\n  enabled: false\ngeocode:\n  jitter_missing: false\n')
            m.validate_manifest(root, 'test')
            target.write_text('slug: test\nschedule:\n  enabled: true\n')
            with self.assertRaises(ValueError):
                m.validate_manifest(root, 'test')

    def test_dry_run_and_repo_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root / 'repo'
            repo.mkdir()
            ledger = root / 'ledger.json'
            with m.locked_ledger(ledger, repo) as box:
                box[0] = {'test': True}
            self.assertFalse(ledger.exists())
            with self.assertRaises(ValueError):
                with m.locked_ledger(repo / 'ledger.json', repo):
                    pass


if __name__ == '__main__':
    unittest.main()
