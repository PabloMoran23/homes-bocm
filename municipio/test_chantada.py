"""Offline parser tests: run with python -m unittest municipio.test_chantada -v."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.chantada import (
    ChantadaAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture(identifier='24329'):
    item = {'id': identifier, 'docnome': 'PLAN XERAL DE ORDENACIÓN URBANA',
            'figura': 'Plan Xeral de Ordenación Urbana', 'fechaaddef': '1985-07-29',
            'fechabop': '1985-09-13', 'fechadog': None, 'fechanormativabop': '1985-09-13'}
    general = {**item, 'menutitle': 'Chantada', 'filesroot': 'documentos/urbanismo/', 'folder': 'CHANTADA'}
    detail = {'datos_xerais': general, 'incidencias_iuris': None, 'elementos': [
        {'description': 'MEMORIA', 'componentes': [{'pathesperado': 'memoria.pdf', 'descripcion': 'Memoria'}]},
        {'description': 'PLANOS', 'componentes': [{'pathesperado': 'plano.jpg', 'descripcion': 'Plano'}]},
    ]}
    return item, detail


class ChantadaParserTests(unittest.TestCase):
    def test_group_documents_and_preserve_date_meanings(self):
        item, detail = fixture()
        row = parse_instrument(parse_inventory([item], 14)[0], detail, {14})
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '1985-07-29')
        self.assertEqual(row['fecha_publicacion_bop'], '1985-09-13')
        self.assertIsNone(row['fecha_publicacion_dog'])
        self.assertEqual(row['siotuga_id'], '24329')
        self.assertEqual(row['codigo_ine'], '27016')
        for field in ('fecha', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
            self.assertNotIn(field, row)
        self.assertFalse(row['publication_ready'])
        self.assertTrue(row['documentos'][0]['url'].endswith('/CHANTADA/documents/memoria.pdf'))

    def test_no_document_leak_between_instruments_and_stable_ids(self):
        first, detail1 = fixture()
        second, detail2 = fixture('28553')
        detail2['elementos'] = [{'description': 'MODIFICACIÓN', 'componentes': [
            {'pathesperado': 'modificacion.pdf', 'descripcion': 'Modificación'}]}]
        one = parse_instrument(first, detail1, {14})
        two = parse_instrument(second, detail2, {14, 16})
        self.assertNotEqual(one['id'], two['id'])
        self.assertEqual(len(two['documentos']), 1)
        self.assertEqual(two['categorias_inventario'], ['planeamento_xeral', 'planeamento_historico'])
        self.assertEqual(one['id'], parse_instrument(first, detail1, {14})['id'])

    def test_empty_categories_and_changed_pagination_schema(self):
        self.assertEqual(parse_inventory(None, 16), [])
        self.assertEqual(parse_inventory([], 18), [])
        for payload in ({'results': [], 'next': '?page=2'}, '<html>error</html>', [{'id': 'form'}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload, 14)

    def test_dates_and_conflicting_duplicates_fail(self):
        item, _ = fixture()
        self.assertEqual(len(parse_inventory([item, item], 14)), 1)
        changed = {**item, 'docnome': 'Another instrument'}
        with self.assertRaises(ValueError):
            parse_inventory([item, changed], 14)
        with self.assertRaises(ValueError):
            parse_inventory([{**item, 'fechaaddef': '2023-02-30'}], 14)

    def test_wrong_municipality_id_dates_repository_and_missing_docs_fail(self):
        item, detail = fixture()
        for field, value in [('id', '999'), ('menutitle', 'Lugo'), ('folder', 'LUGO'),
                             ('fechaaddef', '1986-01-01')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_instrument(item, changed, {14})
        detail['elementos'] = []
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, {14})

    def test_deduplication_keeps_all_group_names(self):
        item, detail = fixture()
        detail['elementos'].append({'description': 'ANEXO', 'componentes': [
            {'pathesperado': 'memoria.pdf', 'descripcion': 'Repeated link'}]})
        row = parse_instrument(item, detail, {14})
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['grupos'], ['MEMORIA', 'ANEXO'])

    def test_manifest_adapter_and_disabled_licences(self):
        manifest = load_manifest('chantada')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '27016')
        self.assertEqual(manifest.provincia, 'Lugo')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ChantadaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session') as session:
            path = Path(directory) / 'licencias.jsonl'
            adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')
            session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
