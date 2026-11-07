"""Offline parser/contract tests; no network or credentials required."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.noia import NoiaAyuntamientoAdapter as Adapter


class NoiaParserTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': '123', 'docnome': 'Plan de prueba', 'figura': 'Plan Especial',
                     'fechaaddef': '2000-02-03', 'fechabop': '2000-03-04',
                     'fechadog': None, 'fechanormativabop': None}
        self.detail = {'datos_xerais': {**self.item, 'denominacion': 'Plan de prueba',
                       'menutitle': 'Noia', 'folder': 'NOIA', 'filesroot': 'documentos/urbanismo/'},
                       'elementos': [{'description': 'MEMORIA', 'componentes': [
                           {'id': '1', 'descripcion': 'Memoria', 'pathesperado': 'test.pdf'},
                           {'id': '2', 'descripcion': 'Plano', 'pathesperado': 'test.jpg'},
                           {'id': '1', 'descripcion': 'Memoria', 'pathesperado': 'test.pdf'}]}]}

    def test_one_instrument_multiple_documents_and_dates(self):
        self.assertEqual(len(Adapter.parse_inventory([self.item, self.item])), 1)
        row = Adapter.parse_project(self.item, self.detail, 13)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2000-02-03')
        self.assertEqual(row['fecha_bop'], '2000-03-04')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '15057')
        self.assertTrue(row['documentos'][0]['url'].endswith('/NOIA/documents/test.pdf'))

    def test_schema_and_pagination_fail_closed(self):
        for payload in ({'results': [self.item], 'next': 2}, {'error': 'expired'}, ['wrong']):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(payload)
        self.assertEqual(Adapter.parse_inventory(None), [])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([{**self.item, 'fechaaddef': '31/12/2000'}])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([self.item, {**self.item, 'docnome': 'Other'}])

    def test_document_and_municipality_guards(self):
        self.detail['datos_xerais']['folder'] = 'OUTRO'
        with self.assertRaises(ValueError):
            Adapter.parse_project(self.item, self.detail, 13)
        self.detail['datos_xerais']['folder'] = 'NOIA'
        self.detail['elementos'] = []
        row = Adapter.parse_project(self.item, self.detail, 13)
        self.assertEqual(row['documentos_status'], 'unavailable')
        self.assertEqual(row['documentos'], [])

    def test_source_inconsistency_retained(self):
        self.item['fechabop'] = '1999-01-01'
        self.detail['datos_xerais']['fechabop'] = '1999-01-01'
        row = Adapter.parse_project(self.item, self.detail, 13)
        self.assertEqual(row['fecha_bop'], '1999-01-01')
        self.assertEqual(len(row['advertencias_fuente']), 1)

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = Adapter('noia').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
