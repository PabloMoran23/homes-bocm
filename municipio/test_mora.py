"""Offline parser and complete-inventory contract checks for Mora."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.mora import MoraAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return {'features': [{'attributes': {
        'OBJECTID': 1753, 'COD_INE': '45106', 'COD_PROV': '45', 'MUNICIPIO': 'Mora',
        'PLAN_': 'NNSS-B', 'NOM_PLAN': 'Normas Subsidiarias tipo b',
        'FECHA_APRO': 617500800000, 'FECHA_ACTU': 1558051200000,
        'ZIP': '45106_MORA.zip',
        'DESCARGA': 'https://ficheroscomunes.castillalamancha.es/planeamiento/TOLEDO/45106_MORA.zip',
    }}]}


class MoraTests(unittest.TestCase):
    def test_real_source_fields_and_document_group(self):
        row, = parse_inventory(fixture())
        self.assertEqual(row['fecha_aprob'], '1989-07-27')
        self.assertEqual(row['fecha_actualizacion_fuente'], '2019-05-17')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['source_attributes'], fixture()['features'][0]['attributes'])

    def test_absent_dates_and_stable_id(self):
        data = fixture()
        data['features'][0]['attributes'].update(OBJECTID=999, FECHA_APRO=None, FECHA_ACTU=None)
        row, = parse_inventory(data)
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_reject_unusable_or_ambiguous_sources(self):
        cases = [{'features': []}, {'error': {'code': 500}},
                 {**fixture(), 'exceededTransferLimit': True}]
        for field, value in [('COD_INE', '45107'), ('COD_PROV', '46'), ('MUNICIPIO', 'Otro'),
                             ('NOM_PLAN', 'Sin planeamiento'), ('DESCARGA', 'https://example.org/form.pdf'),
                             ('FECHA_APRO', '1989-07-27')]:
            data = fixture()
            data['features'][0]['attributes'][field] = value
            cases.append(data)
        duplicate = fixture()
        duplicate['features'] *= 2
        cases.append(duplicate)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_inventory(data)

    def test_all_id_batches_and_atomic_output(self):
        adapter = MoraAyuntamientoAdapter('mora')
        ids = list(range(101))
        features = []
        for i in ids:
            f = copy.deepcopy(fixture()['features'][0])
            f['attributes'].update(OBJECTID=i, PLAN_=f'TEST-{i}')
            features.append(f)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'rows.jsonl'
            with patch.object(adapter, '_get', side_effect=[{'objectIds': ids},
                              {'features': features[:100]}, {'features': features[100:]}]) as get:
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 101)
                self.assertEqual(get.call_count, 3)
                self.assertEqual(get.call_args_list[2].args[0]['objectIds'], '100')
            self.assertEqual(len(output.read_text().splitlines()), 101)
            output.write_text('existing output')
            with patch.object(adapter, '_get', side_effect=[{'objectIds': [1753, 1754]}, fixture()]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'existing output')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('mora')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('45106', 'Toledo'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = MoraAyuntamientoAdapter('mora').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
