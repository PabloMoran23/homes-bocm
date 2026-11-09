import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_susanna import (
    SantaSusannaAyuntamientoAdapter, is_local_instrument, parse_page, parse_project,
)
from municipio.manifest import load_manifest


def listing(ident='121279'):
    return {'codi': ident, 'municipi': 'Santa Susanna', 'instrumentca':
            'Revisió pla general ordenació urbana municipal ',
            'tema': "Revisió del Pla general d'ordenació", 'vigencia': 'SI',
            'registrat': 'SI', 'data': '1982-08-18 00:00:00.0'}


def detail(ident='121279'):
    return {'codintExp': int(ident), 'municipi': 'Santa Susanna',
            'tema': "Revisió del Pla general d'ordenació",
            'tipologiaCA': 'Revisió pla general ordenació urbana municipal ',
            'numComplet': '1982 / 000790 / B', 'dataAprovacio': '1982-05-26',
            'dataPublicacio': '1982-08-18', 'documents': [
                {'idDocument': 206100, 'nomDocument': "Memòria d'informació urbanística.pdf"},
                {'idDocument': 148563, 'nomDocument': 'CU-AD_Aprovació definitiva.pdf'}]}


class SantaSusannaTests(unittest.TestCase):
    def test_dates_grouping_identity(self):
        row = parse_project(listing(), detail())
        self.assertEqual(row['fecha_aprob'], '1982-05-26')
        self.assertEqual(row['fecha_publicacion'], '1982-08-18')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('documentId=148563', row['documentos'][1]['url'])
        d = detail(); d['dataAprovacio'] = d['dataPublicacio'] = None
        self.assertIsNone(parse_project(listing(), d)['fecha_publicacion'])
        self.assertEqual(row['id'], parse_project(listing(), d)['id'])

    def test_scope_and_mismatch(self):
        for change in ({'municipi': 'Barcelona'}, {'instrumentca': 'Conveni urbanístic '},
                       {'instrumentca': 'Modificació de les TUC'}, {'instrumentca': 'Llicència'}):
            row = dict(listing(), **change)
            self.assertFalse(is_local_instrument(row))
        for change in ({'codintExp': 3}, {'municipi': 'Pineda de Mar'},
                       {'documents': None}, {'dataAprovacio': '2025-02-30'}):
            with self.assertRaises(ValueError):
                parse_project(listing(), dict(detail(), **change))
        for payload in ('login', {'totals': 2}, {'totals': -1, 'llistat': []}):
            with self.assertRaises(ValueError):
                parse_page(payload)

    def test_complete_pagination(self):
        pages = [{'totals': 2, 'llistat': [listing('1')]},
                 {'totals': 2, 'llistat': [listing('2')]}]
        adapter = SantaSusannaAyuntamientoAdapter('santa-susanna')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get',
                side_effect=pages + [detail('1'), detail('2')]) as get:
            result = adapter.update_proyectos(Path(tmp) / 'out.jsonl', Path(tmp) / 'state')
            self.assertEqual(result['rows'], 2)
            self.assertEqual([get.call_args_list[i].args[1]['firstRecord'] for i in (0, 1)], [1, 2])
            self.assertEqual(len((Path(tmp) / 'out.jsonl').read_text().splitlines()), 2)

    def test_pagination_failures_do_not_write(self):
        scenarios = [
            [{'totals': 2, 'llistat': [listing()]}, {'totals': 2, 'llistat': []}],
            [{'totals': 2, 'llistat': [listing()]}] * 2,
            [{'totals': 2, 'llistat': [listing()]}, {'totals': 3, 'llistat': [listing('2')]}],
        ]
        for pages in scenarios:
            adapter = SantaSusannaAyuntamientoAdapter('santa-susanna')
            with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=pages):
                target = Path(tmp) / 'out.jsonl'
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(target)
                self.assertFalse(target.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('santa-susanna')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = SantaSusannaAyuntamientoAdapter('santa-susanna').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
