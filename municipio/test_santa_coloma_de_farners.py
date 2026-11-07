"""Offline contract tests for the public RPUC municipal scraper."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_coloma_de_farners import (
    MUNICIPIO, SantaColomaDeFarnersAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

# Subset of the real 42932 response; dates intentionally differ.
ENTRY = {'codi': '42932', 'municipi': MUNICIPIO, 'data': '1995-06-23 00:00:00.0',
         'vigencia': 'SI', 'registrat': 'SI'}
DETAIL = {'codintExp': 42932, 'municipi': MUNICIPIO,
          'tema': "Pla general d'ordenació del municipi",
          'tipologiaCA': "Pla general d'ordenació urbana", 'numComplet': '1993 / 000915 / G',
          'dataAprovacio': '1995-05-03', 'dataPublicacio': '1995-06-23',
          'documents': [{'idDocument': 137970, 'nomDocument': 'Memòria.pdf'},
                        {'idDocument': 137991, 'nomDocument': 'Normes-I.pdf'}]}


class SantaColomaTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Adapter('santa-coloma-de-farners')

    def test_dates_documents_and_identity(self):
        row = self.adapter.parse_project(ENTRY, DETAIL)
        self.assertEqual(row['fecha_aprob'], '1995-05-03')
        self.assertEqual(row['fecha_publicacion'], '1995-06-23')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '17180')
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('documentId=137970', row['documentos'][0]['url'])
        missing = dict(DETAIL, dataAprovacio=None, dataPublicacio=None)
        row = self.adapter.parse_project(ENTRY, missing)
        self.assertIsNone(row['fecha_publicacion'])  # never fall back to listing data
        self.assertIsNone(row['fecha_aprob'])

    def test_rejects_wrong_municipality_identity_and_non_instruments(self):
        for changes in ({'municipi': 'Girona'}, {'codintExp': 42933},
                        {'tipologiaCA': None}, {'tema': None},
                        {'dataAprovacio': '2025-02-30'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.adapter.parse_project(ENTRY, dict(DETAIL, **changes))

    def test_complete_one_based_pagination_and_exclusion(self):
        regional = {'codi': '277143', 'municipi': 'Girona'}
        second = dict(ENTRY, codi='44724')
        pages = [{'totals': 3, 'llistat': [regional, ENTRY]},
                 {'totals': 3, 'llistat': [second]}]
        with patch.object(self.adapter, '_fetch', side_effect=pages) as fetch:
            records, total = self.adapter._inventory()
        self.assertEqual(total, 3)
        self.assertEqual([r['codi'] for r in records], ['42932', '44724'])
        self.assertEqual([c.args[1]['firstRecord'] for c in fetch.call_args_list], [1, 2])
        self.assertTrue(all(c.args[1]['municipi'] == '17180' for c in fetch.call_args_list))

    def test_rejects_truncated_repeated_or_mutating_pages(self):
        for tail in ({'totals': 2, 'llistat': []},
                     {'totals': 2, 'llistat': [ENTRY]},
                     {'totals': 3, 'llistat': [dict(ENTRY, codi='44724')]}):
            with self.subTest(tail=tail), patch.object(self.adapter, '_fetch', side_effect=[
                    {'totals': 2, 'llistat': [ENTRY]}, tail]):
                with self.assertRaises(ValueError):
                    self.adapter._inventory()

    def test_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch.object(self.adapter, '_fetch', side_effect=[
                    {'totals': 1, 'llistat': [ENTRY]}, dict(DETAIL, municipi='Girona')]):
                with self.assertRaises(ValueError):
                    self.adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_snapshot_groups_documents_and_update_refreshes(self):
        duplicate = copy.deepcopy(DETAIL)
        duplicate['documents'].append(duplicate['documents'][0])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            with patch.object(self.adapter, '_fetch', side_effect=[
                    {'totals': 1, 'llistat': [ENTRY]}, duplicate]):
                result = self.adapter.update_proyectos(out, Path(temp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(result['rows'], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_inventory_resource_is_not_a_project(self):
        resource = dict(ENTRY, codi='305399', instrumentca='Inventari municipal sòl i habitatge')
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            with patch.object(self.adapter, '_fetch', side_effect=[
                    {'totals': 2, 'llistat': [ENTRY, resource]}, DETAIL]) as fetch:
                result = self.adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['excluded_non_projects'][0]['rpuc_id'], '305399')
            self.assertEqual(fetch.call_count, 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('santa-coloma-de-farners')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '17180')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'licencias.jsonl'
            self.assertEqual(self.adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
