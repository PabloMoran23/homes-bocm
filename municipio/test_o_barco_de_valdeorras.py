import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.o_barco_de_valdeorras import (
    OBarcoDeValdeorrasAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': '123', 'docnome': 'PXOM 06/01', 'figura': 'Modificación Puntual',
                     'fechaaddef': '2010-12-21', 'fechabop': '2011-01-24',
                     'fechadog': '2001-01-11', 'fechanormativabop': None, 'incidencias_iuris': None}
        self.detail = {'datos_xerais': {**self.item, 'menutitle': 'Barco de Valdeorras, O',
                                      'filesroot': 'documentos/urbanismo/', 'folder': 'OBARCODEVALDEORRAS'},
                       'incidencias_iuris': [{'descripcion': 'Incidencia del instrumento'}],
                       'elementos': [{'description': 'MEMORIA', 'componentes': [
                           {'id': '9', 'pathesperado': 'memoria.pdf', 'descripcion': 'Memoria'},
                           {'id': '9', 'pathesperado': 'memoria.pdf', 'descripcion': 'Memoria'},
                           {'id': '10', 'pathesperado': 'plano.jpg', 'descripcion': 'Plano'}]}]}

    def test_dates_documents_and_provenance(self):
        row = parse_project(self.item, self.detail, 'planeamento_xeral')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2010-12-21')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(row['publicaciones'][1]['fecha'], '2001-01-11')
        self.assertEqual(len(row['advertencias_fuente']), 1)
        self.assertEqual(row['incidencias_iuris'], self.detail['incidencias_iuris'])
        self.assertEqual(row['documentos'][0]['url'],
                         'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/OBARCODEVALDEORRAS/documents/memoria.pdf')
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['fuente_detalle']['parametros']['iddoc'], '123')

    def test_full_array_and_duplicates(self):
        items = [{**self.item, 'id': str(i)} for i in range(120)]
        self.assertEqual(len(parse_inventory(items + items)), 120)
        self.assertEqual(parse_inventory(None), [])
        for payload in ({'data': items, 'recordsTotal': 200}, [self.item, {**self.item, 'docnome': 'other'}], [{}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_detail_guards(self):
        for field, value in [('id', '999'), ('menutitle', 'Ourense'), ('fechabop', '2020-01-01'),
                             ('folder', 'OTHER')]:
            detail = copy.deepcopy(self.detail)
            detail['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_project(self.item, detail, 'planeamento_xeral')
        detail = copy.deepcopy(self.detail)
        detail['elementos'] = []
        row = parse_project(self.item, detail, 'planeamento_xeral')
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentos_status'], 'unavailable_in_source')
        self.assertIn('no document components', row['advertencias_fuente'][-1])

    def test_manifest_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('o-barco-de-valdeorras'))
        self.assertIsInstance(adapter, OBarcoDeValdeorrasAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
            adapter.update_proyectos(Path('unused'), Path('unused-state'))
            backfill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
