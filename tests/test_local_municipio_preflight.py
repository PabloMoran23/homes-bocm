import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('preflight', Path(__file__).resolve().parents[1] / 'scripts/local_municipio_preflight.py')
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def test_publication_workflow_trigger_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github/workflows'
            workflows.mkdir(parents=True)
            target = workflows / 'municipio-post-merge.yml'
            target.write_text('on:\n  workflow_dispatch:\n')
            self.assertEqual(preflight.assert_workflows(root), {'municipio-post-merge.yml': ['workflow_dispatch']})
            target.write_text('on: [push, workflow_dispatch]\n')
            with self.assertRaisesRegex(ValueError, 'Unreviewed workflow'):
                preflight.assert_workflows(root)

    def test_incomplete_batch_cannot_pass_even_with_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            def run(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            run('config', 'user.email', 'test@example.invalid')
            run('config', 'user.name', 'Test')
            run('commit', '--allow-empty', '-qm', 'baseline')
            run('branch', '-M', 'main')
            run('remote', 'add', 'origin', str(root))
            base = run('rev-parse', 'HEAD')
            run('checkout', '-qb', 'batch')
            run('commit', '--allow-empty', '-qm', 'batch [skip deploy]')
            ledger = root.parent / (root.name + '-ledger.json')
            try:
                ledger.write_text(json.dumps({'repo': str(root), 'municipios': []}))
                with self.assertRaisesRegex(ValueError, 'Exactly 50'):
                    preflight.inspect(root, ledger, 'batch-001', base, Path('unused'))
            finally:
                ledger.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
