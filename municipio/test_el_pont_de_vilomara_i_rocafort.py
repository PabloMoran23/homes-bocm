import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.el_pont_de_vilomara_i_rocafort import (
    ElPontDeVilomaraIRocafortAyuntamientoAdapter as Adapter, MUNICIPIO,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def item(n):
    return {'codi': str(n), 'municipi': MUNICIPIO, 'data': '2020-01-01', 'vigencia': 'SI'}


def detail(n):
    return {'codintExp': n, 'municipi': MUNICIPIO, 'tema': 'Pla parcial',
            'numComplet': '2000 / 000001 / N', 'dataAprovacio': '2001-02-03',
            'dataPublicacio': '2001-04-05', 'documents': [
                {'idDocument': 123, 'nomDocument': 'Memòria.pdf'},
                {'idDocument': 124, 'nomDocument': 'Plànols.pdf'}]}


class ParserTests(unittest.TestCase):
    def test_dates_documents_identity(self):
        row = Adapter.parse_instrument(item(1), detail(1))
        self.assertEqual(row['fecha_aprob'], '2001-02-03')
        self.assertEqual(row['fecha_publicacion'], '2001-04-05')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('documentId=123', row['documentos'][0]['url'])
        self.assertEqual(row['codigo_ine'], '08182')

    def test_missing_dates_not_inferred_from_list_date(self):
        d = detail(1)
        d.pop('dataAprovacio'); d.pop('dataPublicacio')
        row = Adapter.parse_instrument(item(1), d)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_invalid_details(self):
        for updates in [{'municipi': 'Barcelona'}, {'codintExp': 2}, {'documents': []},
                        {'dataAprovacio': 'bad'}, {'tema': ''}]:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                Adapter.parse_instrument(item(1), {**detail(1), **updates})
        with self.assertRaises(ValueError):
            Adapter.parse_page({'totals': 2, 'llistat': [{'titulo': 'Llicència form'}]})

    def test_complete_pagination_and_regional_exclusion(self):
        adapter = Adapter('el-pont-de-vilomara-i-rocafort')
        pages = []
        def fetch(endpoint, params):
            if endpoint == 'detall':
                return detail(int(params['codiExpedient']))
            pages.append(params['firstRecord'])
            items = [item(n) for n in range(1, 11)] if len(pages) == 1 else [
                {**item(11), 'municipi': 'Solsona'}]
            return {'totals': 11, 'llistat': items}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=fetch):
            path = Path(tmp) / 'out.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(pages, [1, 2])
            self.assertEqual(result['rows'], 10)
            self.assertEqual(len([json.loads(x) for x in path.read_text().splitlines()]), 10)

    def test_incomplete_or_duplicate_pagination_preserves_output(self):
        for second in [{'totals': 11, 'llistat': []},
                       {'totals': 11, 'llistat': [item(1)]},
                       {'totals': 12, 'llistat': [item(11)]}]:
            adapter = Adapter('el-pont-de-vilomara-i-rocafort')
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'out.jsonl'; path.write_text('previous')
                with patch.object(adapter, '_get', side_effect=[
                        {'totals': 11, 'llistat': [item(n) for n in range(1, 11)]}, second]):
                    with self.assertRaises(ValueError):
                        adapter.backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('el-pont-de-vilomara-i-rocafort')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Barcelona')


if __name__ == '__main__':
    unittest.main()
