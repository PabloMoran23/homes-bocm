"""Offline parser and pagination checks; no network required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cardona import CardonaAyuntamientoAdapter, parse_project, parse_inventory, selected
from municipio.manifest import load_manifest


def entry(code='262286', **changes):
    return {'codi': code, 'municipi': 'Cardona', 'instrumentca': "Pla d'ordenació urbanística municipal",
            'nomComplet': '2012 / 049232 / N', 'tema': 'POUM',
            'vigencia': 'SI', 'data': '2020-10-22 00:00:00.0', **changes}


def detail(code='262286', **changes):
    return {'codintExp': int(code), 'municipi': 'Cardona', 'numComplet': '2012 / 049232 / N',
            'tema': "Pla d'ordenació urbanística municipal", 'tipologiaCA': 'POUM',
            'dataAprovacio': '2015-01-23', 'dataPublicacio': '2020-10-22', **changes}


def tree():
    doc = {'idDocument': 269069, 'nomDocument': 'Memòria.pdf', 'baixa': '0'}
    return [{'label': 'Memòria', 'data': [doc], 'children': [
        {'label': 'Annex', 'data': [doc, {'idDocument': 423704, 'nomDocument': 'Acord.pdf'}]}]}]


class CardonaTests(unittest.TestCase):
    def test_dates_identity_documents_and_no_geometry(self):
        row = parse_project(entry(), detail(), tree())
        self.assertEqual(row['fecha_aprob'], '2015-01-23')
        self.assertEqual(row['fecha_publicacion'], '2020-10-22')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['categorias']), 2)
        self.assertIn('documentId=269069', row['documentos'][0]['url'])
        self.assertEqual(row['id'], 'cardona-rpuc-262286')

    def test_missing_dates_do_not_use_generic_data(self):
        row = parse_project(entry(), detail(dataAprovacio=None, dataPublicacio=None), tree())
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        with self.assertRaises(ValueError):
            parse_project(entry(), detail(dataAprovacio='2025-02-30'), tree())

    def test_exclusions_and_detail_mismatch(self):
        for changes in ({'municipi': 'Barcelona'}, {'instrumentca': 'Conveni urbanístic'},
                        {'instrumentca': 'Delimitació de la TUC'},
                        {'instrumentca': 'Sol·licitud de Llicència'}, {'instrumentca': 'Contractacions'}):
            self.assertFalse(selected(entry(**changes)))
        for changes in ({'codintExp': 1}, {'municipi': 'Súria'}, {'numComplet': 'other'}):
            with self.assertRaises(ValueError):
                parse_project(entry(), detail(**changes), tree())
        with self.assertRaises(ValueError):
            parse_project(entry(), detail(), [])

    def test_inventory_schema(self):
        for payload in ({}, {'infoFiltre': 'Súria', 'totals': 1, 'llistat': [entry()]},
                        {'infoFiltre': 'Cardona', 'totals': '1', 'llistat': []}):
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_complete_pagination_and_atomic_failure(self):
        adapter = CardonaAyuntamientoAdapter()
        offsets = []
        def fetch(endpoint, params):
            if endpoint == 'basica':
                offset = params['firstRecord'] - 1
                offsets.append(offset)
                return {'infoFiltre': 'Cardona', 'totals': 2,
                        'llistat': [entry(str(262286 + offset))]}
            if endpoint == 'detall':
                return detail(params['codiExpedient'])
            return tree()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                self.assertEqual(adapter.backfill_proyectos(out)['rows'], 2)
            self.assertEqual(offsets, [0, 1])
            original = out.read_text()
            bad = {'infoFiltre': 'Cardona', 'totals': 2, 'llistat': [entry()]}
            cases = ([bad, bad], [bad, {**bad, 'llistat': []}],
                     [bad, {**bad, 'totals': 3}])
            for responses in cases:
                with patch.object(adapter, '_fetch', side_effect=copy.deepcopy(responses)):
                    with self.assertRaises(ValueError):
                        adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cardona')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertEqual(manifest.portal.config['ine_code'], '08047')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(CardonaAyuntamientoAdapter().backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
