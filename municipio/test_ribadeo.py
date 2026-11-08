"""Offline parser/contract checks; no network required."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ribadeo import RibadeoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def fixture(key='27886', title='PLAN XERAL DE ORDENACIÓN MUNICIPAL'):
    item = {'id': key, 'docnome': title, 'figura': 'Plan Xeral de Ordenación Municipal',
            'fechaaddef': '2014-11-14', 'fechadog': '2014-12-01',
            'fechabop': '2014-12-29', 'fechanormativabop': None, 'incidencias_iuris': None}
    detail = {'datos_xerais': {**item, 'denominacion': title, 'menutitle': 'Ribadeo',
                              'filesroot': 'documentos/urbanismo/', 'folder': 'RIBADEO'},
              'elementos': [{'description': 'MEMORIA', 'componentes': [
                  {'descripcion': 'Memoria', 'pathesperado': key + 'me001.pdf'}]}]}
    return item, detail


class RibadeoTests(unittest.TestCase):
    def test_dates_provenance_and_no_invented_location(self):
        row = Adapter.parse_detail(*fixture())
        self.assertEqual(row['fecha_aprob'], '2014-11-14')
        self.assertEqual(row['fecha_publicacion_dog'], '2014-12-01')
        self.assertEqual(row['fecha_publicacion_bop'], '2014-12-29')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['url'],
                         'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/RIBADEO/documents/27886me001.pdf')

    def test_all_inventory_rows_and_duplicates(self):
        items = [fixture(str(n))[0] for n in range(100)]
        self.assertEqual(len(Adapter.parse_inventory(items + [items[0]])), 100)
        conflict = copy.deepcopy(items[0]); conflict['docnome'] = 'Different'
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(items + [conflict])

    def test_pagination_envelope_and_forms_fail(self):
        for payload in ({'results': [], 'next': 'page2'}, '<form>Licenza</form>', [{}]):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(payload)

    def test_wrong_municipality_and_mismatched_detail(self):
        item, detail = fixture()
        detail['datos_xerais']['menutitle'] = 'Begonte'
        with self.assertRaisesRegex(ValueError, 'municipality'):
            Adapter.parse_detail(item, detail)
        item, detail = fixture()
        detail['datos_xerais']['fechaaddef'] = '2024-01-01'
        with self.assertRaisesRegex(ValueError, 'dates'):
            Adapter.parse_detail(item, detail)

    def test_missing_documents_explicit(self):
        item, detail = fixture(); detail['elementos'] = None
        row = Adapter.parse_detail(item, detail)
        self.assertFalse(row['documentacion_disponible'])
        self.assertEqual(row['documentos'], [])

    def test_correction_group_preserves_dates_and_documents(self):
        original = Adapter.parse_detail(*fixture())
        item, detail = fixture('28691', 'CE N1 PXOM')
        item['fechaaddef'] = detail['datos_xerais']['fechaaddef'] = '2024-12-18'
        correction = Adapter.parse_detail(item, detail)
        rows = Adapter.group_instruments([correction, original])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fecha_aprob'], '2014-11-14')
        self.assertEqual(rows[0]['correcciones'][0]['fecha_aprob'], '2024-12-18')
        self.assertEqual(len(rows[0]['documentos']), 2)
        with self.assertRaises(ValueError):
            Adapter.group_instruments([correction])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('ribadeo')
        self.assertEqual(manifest.provincia, 'Lugo')
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter('ribadeo')
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session', side_effect=AssertionError('network')):
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
