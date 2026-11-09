import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.muros import MurosAyuntamientoAdapter, parse_inventory, parse_instrument
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    item = {'id': '42', 'fechaaddef': '2010-12-10', 'fechabop': '2010-12-24',
            'fechadog': '2011-01-02', 'fechanormativabop': None}
    info = {**item, 'menutitle': 'Muros', 'denominacion': 'PLAN XERAL', 'figura': 'PXOM',
            'filesroot': 'documentos/urbanismo/', 'folder': 'MUROS'}
    component = {'id': '1', 'descripcion': 'Memoria', 'pathesperado': 'memoria.pdf'}
    detail = {'datos_xerais': info, 'elementos': [
        {'description': 'Memoria', 'componentes': [component, component]},
        {'description': 'Anexos', 'componentes': [component]}]}
    return item, detail


class MurosTests(unittest.TestCase):
    def test_group_documents_and_date_semantics(self):
        item, detail = fixture()
        row = parse_instrument(item, detail)
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['grupos'], ['Memoria', 'Anexos'])
        self.assertEqual(row['fecha_aprob'], '2010-12-10')
        self.assertEqual(row['fecha_publicacion_dog'], '2011-01-02')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '15053')

    def test_inventory_complete_array_and_duplicates(self):
        item, _ = fixture()
        self.assertEqual(parse_inventory([item, item]), [item])
        self.assertEqual(parse_inventory(None), [])
        for envelope in ({'results': [item], 'next': 'page2'}, 'not JSON records'):
            with self.assertRaises(ValueError):
                parse_inventory(envelope)
        with self.assertRaises(ValueError):
            parse_inventory([item, {**item, 'fechaaddef': None}])

    def test_reject_wrong_provenance_missing_documents_and_dates(self):
        item, original = fixture()
        for field, value in [('menutitle', 'Muras'), ('id', '43'), ('fechaaddef', None),
                             ('filesroot', 'https://unrelated.invalid/')]:
            detail = copy.deepcopy(original)
            detail['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(item, detail)
        original['elementos'] = []
        with self.assertRaises(ValueError):
            parse_instrument(item, original)

    def test_manifest_resolution_and_disabled_licences(self):
        manifest = load_manifest('muros')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MurosAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
