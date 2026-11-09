import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.soutomaior import SoutomaiorAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


class SoutomaiorTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': '28065', 'docnome': 'PXOM Soutomaior', 'figura': 'Plan Xeral',
                     'fechaaddef': '2017-03-13', 'fechadog': '2017-03-30',
                     'fechabop': '2017-07-31', 'fechanormativabop': None}
        general = dict(self.item, menutitle='Soutomaior', folder='SOUTOMAIOR', filesroot='documentos/urbanismo/')
        self.detail = {'datos_xerais': general, 'incidencias_iuris': None,
                       'elementos': [{'description': 'Memoria', 'componentes': [
                           {'id': '1', 'descripcion': 'Memoria', 'pathesperado': '28065me.pdf'},
                           {'id': '2', 'descripcion': 'Plano', 'pathesperado': '28065po.jpg'}]}]}

    def test_grouping_dates_and_provenance(self):
        items = Adapter.parse_inventory([self.item, self.item], 14)
        self.assertEqual(len(items), 1)
        row = Adapter.parse_project(items[0], self.detail)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2017-03-13')
        self.assertEqual(row['fecha_publicacion_dog'], '2017-03-30')
        self.assertEqual(row['fecha_publicacion_bop'], '2017-07-31')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '36053')
        self.assertEqual(row['documentos'][0]['url'], 'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/SOUTOMAIOR/documents/28065me.pdf')
        self.assertEqual(row['provenance']['detail_parameters']['iddoc'], '28065')

    def test_no_local_page_limit(self):
        items = [dict(self.item, id=str(n)) for n in range(100)]
        self.assertEqual(len(Adapter.parse_inventory(items, 13)), 100)
        self.assertEqual(Adapter.parse_inventory(None, 18), [])
        for payload in ({'data': items, 'next': '?page=2'}, '<html>error</html>', [{}]):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(payload, 14)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([self.item, dict(self.item, docnome='Other')], 14)

    def test_identity_documents_and_dates_fail_closed(self):
        item = Adapter.parse_inventory([self.item], 14)[0]
        for field, value in [('id', '22'), ('menutitle', 'Vigo'), ('folder', 'VIGO'),
                             ('fechaaddef', '2017-03-14')]:
            detail = copy.deepcopy(self.detail)
            detail['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                Adapter.parse_project(item, detail)
        detail = copy.deepcopy(self.detail)
        detail['elementos'] = None
        row = Adapter.parse_project(item, detail)
        self.assertEqual(row['documentos'], [])
        self.assertIsNone(row['url_documento'])
        self.assertIn('no disponibles', row['documentos_status'])
        detail['elementos'] = []
        with self.assertRaises(ValueError):
            Adapter.parse_project(item, detail)
        detail = copy.deepcopy(self.detail)
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../elsewhere.pdf'
        with self.assertRaises(ValueError):
            Adapter.parse_project(item, detail)

    def test_historical_and_manifest_contract(self):
        item = Adapter.parse_inventory([self.item], 16)[0]
        row = Adapter.parse_project(item, self.detail)
        self.assertEqual(row['vigencia'], 'histórico según inventario')
        adapter = load_portal_adapter(load_manifest('soutomaior'))
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.soutomaior.requests.Session', side_effect=AssertionError('network')):
                self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
