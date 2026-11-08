import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.rafelbunyol import RafelbunyolAyuntamientoAdapter as Adapter, SOURCE
from municipio.entity_policy import classify
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def item(number, filename, date='01-07-2010'):
    return (f'<p>Número {number} - Normes subsidiàries</p><p>Fecha : {date}</p>'
            f'<a href="/storage/uploads/{filename}.pdf">Enlace</a><hr>')


def inventory(items):
    return '<table><tbody><td>Modificacions puntuals</td><td>' + items + '</td></tbody></table>'


class RafelbunyolTests(unittest.TestCase):
    def test_groups_verified_catalogue_errors_and_preserves_provenance(self):
        html = inventory(item('8', 'modificacion_puntual_8_0') +
                         item('8.2', 'modificacion_puntual_8.2') +
                         item('11', 'modificacion_puntual_11') +
                         item('12', 'Mod_11_NNSS'))
        rows = Adapter.parse_inventory(html)
        self.assertEqual([r['numero_modificacion'] for r in rows], ['8', '11'])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['geometry'])
            self.assertEqual(classify(row)['entity_type'], 'expediente')
            self.assertEqual(row['documentos'][0]['fecha_catalogo'], '2010-07-01')
            self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        self.assertIn('Número 12', rows[1]['documentos'][1]['titulo'])

    def test_duplicate_documents_do_not_create_projects(self):
        rows = Adapter.parse_inventory(inventory(item('4', 'mod4') * 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)

    def test_fails_on_uncovered_pagination_or_source_changes(self):
        valid = inventory(item('4', 'mod4'))
        cases = [valid + '<a rel="next" href="?page=2">2</a>',
                 valid + '<a href="?pagina=2">2</a>', '<p>Licence application</p>',
                 inventory(''), inventory(item('12', 'different_document')),
                 valid.replace('01-07-2010', '31-02-2010'),
                 valid.replace('/storage/uploads/mod4.pdf', 'https://other.example/file.pdf')]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_manifest_loads_and_disabled_licences_are_empty(self):
        manifest = load_manifest('rafelbunyol')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')

    def test_failed_live_refresh_preserves_previous_output(self):
        adapter = Adapter('rafelbunyol')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text(json.dumps({'id': 'previous'}) + '\n')
            with patch('municipio.adapters.rafelbunyol.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(json.loads(path.read_text())['id'], 'previous')


if __name__ == '__main__':
    unittest.main()
