import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.moya import PACKAGE_ID, MoyaAyuntamientoAdapter, parse_index, parse_package
from municipio.manifest import load_manifest


def fixture():
    title = 'Aprobación Definitiva de Estudio de Detalle en Calle Argentina y Camino Moreto de Moya'
    publication = ', publicado el 10/06/2020 en el BOC 115/20 y el 29/01/2024 en el BOP 013/24'
    return {'success': True, 'result': {
        'id': PACKAGE_ID, 'name': 'planeamiento-urbanistico-de-moya', 'num_resources': 2,
        'resources': [
            {'id': 'index', 'name': title + publication, 'description': '', 'format': 'PDF',
             'url': 'https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Moya/ed-arg-mor/indice.html'},
            {'id': 'zip', 'name': title, 'description': publication, 'format': 'SIPU',
             'url': 'https://opendata.sitcan.es/example.zip'},
        ]}}


class MoyaTests(unittest.TestCase):
    def test_grouping_dates_and_stable_identity(self):
        payload = fixture()
        row, = parse_package(payload)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual([p['fecha_publicacion'] for p in row['publicaciones']], ['2020-06-10', '2024-01-29'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        payload['result']['resources'].reverse()
        self.assertEqual(row['id'], parse_package(payload)[0]['id'])

    def test_reject_incomplete_wrong_municipality_and_forms(self):
        for change in ('count', 'municipality', 'form', 'duplicate'):
            payload = copy.deepcopy(fixture())
            if change == 'count':
                payload['result']['num_resources'] = 3
            elif change == 'municipality':
                payload['result']['id'] = 'other'
            elif change == 'form':
                payload['result']['resources'][0]['name'] = 'Solicitud de licencia urbanística'
            else:
                payload['result']['resources'][1]['id'] = 'index'
            with self.assertRaises(ValueError):
                parse_package(payload)

    def test_index_links_and_pagination(self):
        url = 'https://www.idecanarias.es/Moya/plan/indice.html'
        html = '<a href="TNP/memoria.pdf">Memoria</a><a href="TNP/memoria.pdf">Duplicado</a>'
        docs = parse_index(html, url)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['url'], 'https://www.idecanarias.es/Moya/plan/TNP/memoria.pdf')
        for invalid in ('<p>No documents</p>', html + '<a href="page2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_index(invalid, url)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('moya')
        self.assertEqual(manifest.provincia, 'Las Palmas')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = MoyaAyuntamientoAdapter('moya').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
