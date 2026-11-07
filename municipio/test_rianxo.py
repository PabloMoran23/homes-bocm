import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.rianxo import SOURCE, RianxoAyuntamientoAdapter, parse_page
from municipio.manifest import load_manifest

CURRENT = '''<div class="journal-content-article">
<h1>Documento de aprobación provisional</h1>
<p>Documento do Plan Xeral de Ordenación de Rianxo aprobado provisionalmente na sesión do Pleno da Corporación do 11 de maio de 2023.</p>
<a href="/documents/1/normativa.pdf/uuid?t=12">Normativa</a>
<a href="/documents/1/normativa.pdf/uuid?t=34">Duplicado</a>
<a href="/documents/1/plano.pdf/uuid2"><img src="x"></a>
<a href="https://foreign.example/a.pdf">Unrelated</a>
</div><div class="journal-content-article"><h2>Documentos anteriores</h2>
<a href="/pxom-aprobacion-inicial">Documento de aprobación inicial</a></div>'''
INITIAL = '''<div class="journal-content-article"><h1>Documento de aprobación inicial (maio 2014)</h1>
<a href="/ftp/resumo.pdf">Resumo executivo</a>
<a href="/documents/2/anuncio.pdf/uuid">Anuncio publicado no DOGA de 3 de decembro de 2014</a></div>'''


class RianxoTests(unittest.TestCase):
    def test_documents_dates_and_deduplication(self):
        docs, previous, agreement = parse_page(CURRENT, SOURCE, 'provisional')
        self.assertEqual(len(docs), 2)
        self.assertEqual(agreement, '2023-05-11')
        self.assertEqual(previous, [SOURCE + '-aprobacion-inicial'])
        self.assertIn('?t=12', docs[0]['url'])
        self.assertTrue(docs[1]['titulo'])
        self.assertEqual(docs[0]['source_url'], SOURCE)

    def test_group_phases_without_publication_date_inference(self):
        adapter = RianxoAyuntamientoAdapter('rianxo')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=[CURRENT, INITIAL]):
            output = Path(folder) / 'out.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(rows[0]['documentos']), 4)
            self.assertNotIn('fecha_publicacion', rows[0])
            self.assertNotIn('fecha_aprob', rows[0])
            self.assertNotIn('lat', rows[0])
            self.assertEqual(rows[0]['fase'], 'aprobacion_provisional')

    def test_reject_pagination(self):
        for control in ['<a href="?page=2" rel="next">2</a>', '<a href="javascript:;">Seguinte</a>']:
            with self.subTest(control=control), self.assertRaises(ValueError):
                parse_page(CURRENT + control, SOURCE, 'provisional')

    def test_missing_or_changed_source_fails(self):
        for html in ['', CURRENT.replace('aprobado provisionalmente na sesión', 'texto cambiado'),
                     '<div class="journal-content-article">Documento de aprobación inicial</div>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, SOURCE, 'provisional')

    def test_historical_fetch_failure_preserves_output(self):
        adapter = RianxoAyuntamientoAdapter('rianxo')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=[CURRENT, RuntimeError('offline')]):
            output = Path(folder) / 'out.jsonl'
            output.write_text('previous output')
            with self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous output')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('rianxo')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            self.assertTrue(RianxoAyuntamientoAdapter('rianxo').backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
