"""Offline parser contracts; fixtures are synthetic, not production records."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arico import (
    AricoAyuntamientoAdapter, DATASET, parse_catalogue, parse_document_index,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


TITLE = 'Aprobación Definitiva de Plan Parcial Ejemplo de Arico por Pleno COTMAC el 03/11/2004'
INDEX = 'https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Aric/999/indice.html'


def fixture():
    resources = [
        {'id': 'a', 'name': TITLE, 'url': INDEX, 'format': 'HTML',
         'description': 'Documentación de ' + TITLE + ', publicado el 14/01/2005 en el BOC 009/05'},
        {'id': 'b', 'name': TITLE, 'url': 'https://opendata.sitcan.es/test.zip',
         'format': 'ZIP', 'description': 'Sistematización de ' + TITLE},
    ]
    return {'success': True, 'result': {'name': DATASET, 'title': 'Planeamiento urbanístico de Arico',
                                       'num_resources': 2, 'resources': resources}}


class AricoParserTests(unittest.TestCase):
    def test_group_dates_and_provenance(self):
        rows = parse_catalogue(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2004-11-03')
        self.assertEqual(row['fecha_publicacion'], '2005-01-14')
        self.assertEqual(row['codigo_ine'], '38005')
        self.assertNotIn('fecha', row)
        self.assertNotIn('lat', row)

    def test_missing_dates_not_inferred_from_cms(self):
        data = fixture()
        for r in data['result']['resources']:
            r['description'] = 'Documentación del plan'
            r['created'] = '2026-11-07'
        row = parse_catalogue(data)[0]
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('fecha_publicacion', row)

    def test_reject_incomplete_wrong_and_empty_inventory(self):
        for change in ('count', 'municipality', 'empty', 'licence'):
            data = fixture()
            if change == 'count': data['result']['num_resources'] = 3
            if change == 'municipality': data['result']['name'] = 'other'
            if change == 'empty': data['result'].update(resources=[], num_resources=0)
            if change == 'licence': data['result']['resources'][0]['name'] = 'Solicitud de licencia'
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_catalogue(data)

    def test_document_resolution_isolation_and_deduplication(self):
        docs = parse_document_index('<a href="TIP/a.pdf">Memoria</a><a href="TIP/a.pdf">Memoria</a>', INDEX)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['url'], INDEX.replace('indice.html', 'TIP/a.pdf'))
        for html in ('<a href="../998/a.pdf">Otro</a>', '<p>Sin documentos</p>'):
            with self.assertRaises(ValueError): parse_document_index(html, INDEX)

    def test_shared_index_warning_and_unique_ids(self):
        data = fixture()
        other = copy.deepcopy(data['result']['resources'][0])
        other.update(id='c', name=TITLE.replace('Ejemplo', 'Otro'))
        data['result']['resources'].append(other)
        data['result']['num_resources'] = 3
        rows = parse_catalogue(data)
        self.assertEqual(len({r['id'] for r in rows}), 2)
        self.assertTrue(all(r['source_warnings'] for r in rows))

    def test_conflicting_dates_fail(self):
        data = fixture()
        data['result']['resources'][1]['description'] = TITLE.replace('03/11/2004', '04/11/2004')
        with self.assertRaises(ValueError): parse_catalogue(data)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('arico')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '38005')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, AricoAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            with patch('requests.Session.get', side_effect=AssertionError('Network forbidden')):
                adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
