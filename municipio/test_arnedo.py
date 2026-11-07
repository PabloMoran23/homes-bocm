import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arnedo import ArnedoAyuntamientoAdapter as Adapter
from municipio.adapters.arnedo import BASE
from municipio.manifest import load_manifest, load_yaml


def entry(key='1', title='Normativa PGM', category='Normativa', count=1):
    return {'dboid': key, 'descriptionProc': title,
            'tablon': {'dboid': category, 'description': category, 'numOpenResolutions': count},
            'pubDateIni': {'year': 2024, 'month': 4, 'day': 19},
            'resolutionDate': {'year': 2023, 'month': 12, 'day': 1},
            'remitent': {'description': 'Urbanismo y Medio Ambiente'}}


def inventory(rows):
    return '<h3>PLAN GENERAL DE ORDENACIÓN URBANA</h3><script>var dataset_TR_PLAN_GENURB = ' + json.dumps(rows) + ';</script>'


def detail(title='Normativa PGM', cud='123'):
    return '<div>' + title + '</div><a href="/sta/docs/GetDocumentServlet?CUD=' + cud + '&amp;HASH_CUD=abc&amp;APP_CODE=STA">Acuerdo</a>'


class ArnedoTests(unittest.TestCase):
    def test_groups_normative_and_all_maps_with_provenance(self):
        entries = [entry(), entry('2', 'P-1 ordenación', 'Planos', 2), entry('3', 'P-2 ordenación', 'Planos', 2)]
        parsed = Adapter.parse_inventory(inventory(entries))
        docs = [d for r in parsed for d in Adapter.parse_documents(detail(r['descriptionProc'], r['dboid']), r)]
        rows = Adapter.build_projects(parsed, docs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['fecha_publicacion'], '2024-04-19')
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fase'])
        self.assertIsNone(rows[0]['lat'])
        self.assertFalse(rows[0]['publication_ready'])
        self.assertEqual(docs[1]['publicacion_id'], '2')
        self.assertTrue(docs[1]['url'].startswith(BASE))

    def test_reads_beyond_ui_page_of_ten(self):
        entries = [entry()] + [entry(str(i), 'P-' + str(i), 'Planos', 31) for i in range(2, 33)]
        self.assertEqual(len(Adapter.parse_inventory(inventory(entries))), 32)

    def test_rejects_empty_wrong_or_incomplete_inventory(self):
        for html in ['', '<p>Solicitud licencia de obras</p>', inventory([]), inventory([entry(count=2)]),
                     inventory([entry(), entry()]), inventory([entry(title='P-1')]),
                     inventory([entry()]) + '<script>serverSide: true</script>']:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_missing_changed_or_foreign_document_fails(self):
        for html in ['<p>Normativa PGM</p>', detail('Otro plan'),
                     detail().replace('/sta/docs/', 'https://example.org/sta/docs/'),
                     detail().replace('HASH_CUD', 'other')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_documents(html, entry())
        with self.assertRaises(ValueError):
            Adapter.build_projects([entry()], [])

    def test_mixed_publication_dates_not_single_approval(self):
        one = entry()
        two = entry('2', 'P-1', 'Planos')
        two['pubDateIni']['day'] = 20
        docs = [d for r in [one, two] for d in Adapter.parse_documents(detail(r['descriptionProc']), r)]
        row = Adapter.build_projects([one, two], docs)[0]
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(docs[1]['fecha_publicacion'], '2024-04-20')

    def test_failure_preserves_existing_output_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            adapter = Adapter()
            with patch.object(adapter, '_fetch', return_value='<p>changed source</p>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('arnedo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '26018')
        self.assertEqual(manifest.provincia, 'La Rioja')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.arnedo:ArnedoAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
