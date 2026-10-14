import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from municipio.refresh_dispatch import bounded_review, review


class ReviewTest(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.output=Path(self.tmp.name)/'output'
        self.output.mkdir()
        (self.output/'proyectos.jsonl').write_text('valid original\n')
        self.manifest=SimpleNamespace(slug='test',output_dir=self.output,
            proyectos=SimpleNamespace(enabled=True),licencias=SimpleNamespace(enabled=False))

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_ok_is_incomplete_and_restores_valid_output(self):
        def runner(manifest):
            (manifest.output_dir/'proyectos.jsonl').write_text('partial')
            return {'status':'ok','rows':0}
        with patch('municipio.refresh_dispatch.load_manifest',return_value=self.manifest), patch('municipio.proyectos_runner.update',side_effect=runner), patch('municipio.orchestrator.run') as sync:
            result=review('test')
        self.assertFalse(result['complete'])
        self.assertFalse(result['reviewed'])
        self.assertIn('review_complete',result['error'])
        sync.assert_not_called()
        self.assertEqual((self.output/'proyectos.jsonl').read_text(),'valid original\n')

    def test_timeout_restores_previous_output(self):
        def blocked(slug):
            (self.output/'proyectos.jsonl').write_text('partial')
            time.sleep(10)
        with patch('municipio.refresh_dispatch.load_manifest',return_value=self.manifest), patch('municipio.refresh_dispatch.review',side_effect=blocked), patch('municipio.refresh_dispatch.REVIEW_SECONDS',.1):
            result=bounded_review('test')
        self.assertFalse(result['complete'])
        self.assertIn('timeout',result['error'])
        self.assertEqual((self.output/'proyectos.jsonl').read_text(),'valid original\n')

    def test_source_review_and_db_write_are_independent(self):
        with patch('municipio.refresh_dispatch.load_manifest',return_value=self.manifest), patch('municipio.proyectos_runner.update',return_value={'review_complete':True}), patch('municipio.orchestrator.run',side_effect=[{'steps':{}},{'steps':{}},{'steps':{'sync':{'error':'DB down'}}}]):
            result=review('test')
        self.assertFalse(result['complete'])
        self.assertTrue(result['reviewed'])
        self.assertFalse(result['written'])
