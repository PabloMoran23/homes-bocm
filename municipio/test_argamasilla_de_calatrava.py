import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.argamasilla_de_calatrava import (
    ArgamasillaDeCalatravaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def inventory():
    return {'features': [{'attributes': {
        'OBJECTID': 107, 'COD_PROV': '13', 'PROVINCIA': 'CIUDAD REAL',
        'COD_INE': '13020', 'MUNICIPIO': 'Argamasilla de Calatrava',
        'PLAN_': 'NNSS', 'NOM_PLAN': 'Normas Subsidiarias_b',
        'DESCARGA': 'https://ficheroscomunes.castillalamancha.es/planeamiento/SIU/13020_ARGAMASILLA_DE_CALATRAVA.zip',
    }}]}


class PlanningTests(unittest.TestCase):
    def test_grouped_instrument_without_invented_dates_or_geometry(self):
        payload = inventory()
        payload['features'] *= 2
        rows = parse_inventory(payload)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['codigo_ine'], '13020')
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])
        changed = inventory()
        changed['features'][0]['attributes']['OBJECTID'] = 900
        self.assertEqual(row['id'], parse_inventory(changed)[0]['id'])

    def test_reject_wrong_municipality_source_drift_and_truncation(self):
        for field, value in [('COD_INE', '13019'), ('PROVINCIA', 'TOLEDO'),
                             ('MUNICIPIO', 'Argamasilla de Alba'), ('PLAN_', 'POM'),
                             ('DESCARGA', 'https://example.org/form.pdf')]:
            payload = inventory()
            payload['features'][0]['attributes'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_inventory(payload)
        for payload in ({'features': []}, {'error': {'code': 500}},
                        {**inventory(), 'exceededTransferLimit': True}):
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_all_id_batches_and_missing_batch_preserves_previous_output(self):
        adapter = ArgamasillaDeCalatravaAyuntamientoAdapter('argamasilla-de-calatrava')
        features = []
        for i in range(101):
            f = copy.deepcopy(inventory()['features'][0])
            f['attributes']['OBJECTID'] = i
            features.append(f)
        # Distinct inventory rows referring to one package are ambiguous, and
        # must fail only after all IDs have been fetched (no page truncation).
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous\n')
            responses = [{'objectIds': list(range(101)), 'objectIdFieldName': 'OBJECTID'},
                         {'features': features[:100]}, {'features': features[100:]}]
            with patch.object(adapter, '_get', side_effect=responses) as fetch:
                with self.assertRaisesRegex(ValueError, 'Conflicting'):
                    adapter.backfill_proyectos(out)
                self.assertEqual(fetch.call_count, 3)
                self.assertEqual(fetch.call_args_list[2].args[1]['objectIds'], '100')
            self.assertEqual(out.read_text(), 'previous\n')
            with patch.object(adapter, '_get', side_effect=[responses[0], {'features': []}]):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_manifest_and_adapter_snapshot(self):
        manifest = load_manifest('argamasilla-de-calatrava')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        adapter = ArgamasillaDeCalatravaAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_get', side_effect=[
                {'objectIds': [107], 'objectIdFieldName': 'OBJECTID'}, inventory()
            ]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '13020')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
