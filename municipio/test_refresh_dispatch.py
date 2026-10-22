import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from municipio.manifest import load_manifest
from municipio.refresh_dispatch import bounded_review, review


class ReviewTest(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.output=Path(self.tmp.name)/'output'
        self.output.mkdir()
        (self.output/'proyectos.jsonl').write_text('valid original\n')
        self.manifest=load_manifest('oviedo')
        self.manifest._output_dir=self.output
        self.manifest.licencias.enabled=False
        self.manifest.proyectos.enabled=True
        self.job={'slug':'oviedo','token':'test-token'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_ok_is_incomplete_and_does_not_touch_canonical_output(self):
        def runner(manifest):
            self.assertNotEqual(manifest.output_dir,self.output)
            (manifest.output_dir/'proyectos.jsonl').write_text('partial')
            return {'status':'ok','rows':0}
        with patch('municipio.refresh_dispatch.load_manifest',return_value=self.manifest), patch('municipio.proyectos_runner.update',side_effect=runner), patch('municipio.orchestrator.run') as sync:
            result=review(self.job)
        self.assertFalse(result['complete'])
        self.assertFalse(result['reviewed'])
        self.assertIn('review_complete',result['error'])
        sync.assert_not_called()
        self.assertEqual((self.output/'proyectos.jsonl').read_text(),'valid original\n')

    def test_timeout_does_not_modify_canonical_output(self):
        with patch('municipio.refresh_dispatch.review',side_effect=lambda job:time.sleep(10)), patch('municipio.refresh_dispatch.REVIEW_SECONDS',.1):
            result=bounded_review(self.job)
        self.assertFalse(result['complete'])
        self.assertIn('timeout',result['error'])
        self.assertEqual((self.output/'proyectos.jsonl').read_text(),'valid original\n')

    def test_source_review_and_db_write_are_independent(self):
        with patch('municipio.refresh_dispatch.load_manifest',return_value=self.manifest), patch('municipio.proyectos_runner.update',return_value={'review_complete':True}), patch('municipio.orchestrator.run',return_value={'steps':{}}), patch('ingest.connect',side_effect=RuntimeError('DB down')):
            result=review(self.job)
        self.assertFalse(result['complete'])
        self.assertTrue(result['reviewed'])
        self.assertFalse(result['written'])

    def test_refresh_workflow_keeps_legacy_schedule(self):
        root=Path(__file__).resolve().parents[1]
        legacy=(root/'.github/workflows/refresh-municipios.yml').read_text()
        self.assertIn('17 */4 * * *',legacy)
        self.assertIn('python3 -m municipio schedule run',legacy)
        self.assertNotIn('refresh_dispatch',legacy)

    def test_legacy_timeout_still_defers_by_default(self):
        from municipio.orchestrator import RUNNERS, run
        def timeout(manifest):
            raise TimeoutError('legacy timeout')
        with patch.dict(RUNNERS,{'enrich_geometry':timeout}), patch('municipio.orchestrator.park_manifest') as park:
            result=run(self.manifest,'enrich_geometry')
        self.assertEqual(result['retry'],'dead_letter')
        park.assert_called_once()
        self.assertEqual(park.call_args.kwargs['step'], 'enrich_geometry')

    def test_staging_orchestrator_rejects_sync_steps(self):
        from municipio.orchestrator import run
        with self.assertRaisesRegex(ValueError,'Staging'):
            run(self.manifest,'sync_supabase',staging=True)
        with self.assertRaisesRegex(ValueError,'Staging'):
            run(self.manifest,'update',staging=True)
