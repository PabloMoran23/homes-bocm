import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.montblanc import MontblancAyuntamientoAdapter, parse_project
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    item = {'codi': '30050', 'municipi': 'Montblanc', 'vigencia': 'SI', 'registrat': 'SI'}
    detail = {'codintExp': 30050, 'municipi': 'Montblanc', 'codiRang': 'PG',
              'tema': 'revisió-adaptació del Pla general', 'tipologiaCA': 'Revisió pla general',
              'dataAprovacio': '1998-01-28', 'dataPublicacio': '1998-03-27',
              'numComplet': '1997 / 000524 / T'}
    tree = [{'label': 'Resolucions', 'data': None, 'children': [
        {'label': 'Acord', 'data': [{'idDocument': 47567, 'nomDocument': 'Aprovació.pdf'}], 'children': []}]},
        {'label': 'Normativa', 'data': [{'idDocument': 47571, 'nomDocument': 'Normativa.pdf'}]}]
    return item, detail, tree


class MontblancTests(unittest.TestCase):
    def test_real_field_semantics_and_grouping(self):
        row = parse_project(*fixture())
        self.assertEqual(row['fecha_aprob'], '1998-01-28')
        self.assertEqual(row['fecha_publicacion'], '1998-03-27')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('documentId=47567', row['documentos'][0]['url'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])

    def test_missing_dates_are_not_invented(self):
        item, detail, tree = fixture()
        detail['dataAprovacio'] = None
        detail['dataPublicacio'] = None
        row = parse_project(item, detail, tree)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_wrong_identity_empty_documents_and_invalid_date(self):
        for field, value in [('codintExp', 999), ('municipi', 'Tarragona'), ('dataAprovacio', '2025-02-30')]:
            item, detail, tree = fixture()
            detail[field] = value
            with self.assertRaises(ValueError):
                parse_project(item, detail, tree)
        item, detail, _ = fixture()
        with self.assertRaises(ValueError):
            parse_project(item, detail, [])

    def test_agreement_is_not_a_plan(self):
        item, detail, tree = fixture()
        detail['codiRang'] = 'CNV'
        self.assertIsNone(parse_project(item, detail, tree))

    def test_pagination_complete_and_repeated_page_fails(self):
        adapter = MontblancAyuntamientoAdapter('montblanc')
        pages = [{'totals': 3, 'llistat': [{'codi': '1'}, {'codi': '2'}]},
                 {'totals': 3, 'llistat': [{'codi': '3'}]}]
        with patch.object(adapter, '_get', side_effect=pages) as get:
            self.assertEqual(len(adapter._inventory(None)), 3)
            self.assertEqual([c.args[2]['firstRecord'] for c in get.call_args_list], [1, 2])
        for bad in [pages[0], {'totals': 3, 'llistat': []}, {'totals': 4, 'llistat': [{'codi': '3'}]}]:
            with patch.object(adapter, '_get', side_effect=[pages[0], bad]):
                with self.assertRaises(ValueError):
                    adapter._inventory(None)

    def test_manifest_and_extraction_exclude_other_municipality(self):
        adapter = load_portal_adapter(load_manifest('montblanc'))
        item, detail, tree = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_inventory', return_value=[item, {'codi': '1', 'municipi': 'Barcelona'}]), patch.object(adapter, '_get', side_effect=[detail, tree]):
                result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '43086')


if __name__ == '__main__':
    unittest.main()
