import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villarrubia_de_los_ojos import (
    VillarrubiaDeLosOjosAyuntamientoAdapter, parse_features,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def feature(oid=1104):
    return {'attributes': {
        'OBJECTID': oid, 'COD_INE': '13096', 'COD_PROV': '13',
        'MUNICIPIO': 'Villarrubia de los Ojos', 'PLAN_': 'POM',
        'NOM_PLAN': 'Plan de Ordenación Municipal', 'FECHA_APRO': 1466553600000,
        'FECHA_ACTU': 1543449600000, 'DISPONIBLE': 'SI',
        'ZIP': '13096_VILLARRUBIA_DE_LOS_OJOS.zip',
        'DESCARGA': 'https://ficheroscomunes.castillalamancha.es/planeamiento/CIUDAD_REAL/13096_VILLARRUBIA_DE_LOS_OJOS.zip',
    }}


class PlanningTests(unittest.TestCase):
    def test_dates_provenance_and_no_invented_geometry(self):
        row = parse_features({'features': [feature()]})[0]
        self.assertEqual(row['fecha_aprob'], '2016-06-22')
        self.assertEqual(row['fecha_actualizacion_inventario'], '2018-11-29')
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '13096')
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['source'], 'administracion_autonomica')

    def test_group_same_instrument_and_stable_id(self):
        a = feature()
        b = feature(9999)
        rows = parse_features({'features': [a, b]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], parse_features({'features': [b]})[0]['id'])
        b['attributes']['FECHA_APRO'] = None
        with self.assertRaises(ValueError):
            parse_features({'features': [a, b]})

    def test_reject_wrong_municipality_and_unusable_documents(self):
        for key, value in [('COD_INE', '45195'), ('COD_PROV', '45'),
                           ('MUNICIPIO', 'Villarrubia de Santiago'), ('PLAN_', 'formulario'),
                           ('DESCARGA', 'https://example.org/file.zip'), ('DISPONIBLE', 'NO')]:
            f = feature()
            f['attributes'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_features({'features': [f]})

    def test_reject_empty_errors_and_truncation(self):
        for payload in [{}, {'features': []}, {'error': {'message': 'failure'}},
                        {'features': [feature()], 'exceededTransferLimit': True}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_features(payload)

    def test_missing_date_is_not_filled(self):
        f = feature()
        f['attributes']['FECHA_APRO'] = None
        self.assertIsNone(parse_features({'features': [f]})[0]['fecha_aprob'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('villarrubia-de-los-ojos')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '13096')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'licencias.jsonl'
            result = load_portal_adapter(manifest).backfill_licencias(output)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(output.read_text(), '')

    def test_all_ids_in_multiple_batches_grouped(self):
        adapter = VillarrubiaDeLosOjosAyuntamientoAdapter('villarrubia-de-los-ojos')
        ids = list(range(101))
        responses = [{'objectIds': ids, 'objectIdFieldName': 'OBJECTID'},
                     {'features': [feature(i) for i in ids[:100]]},
                     {'features': [feature(100)]}]
        with tempfile.TemporaryDirectory() as td, patch.object(adapter, '_query', side_effect=responses) as query, \
                patch('municipio.adapters.villarrubia_de_los_ojos.requests.Session') as session:
            download = session.return_value.__enter__.return_value.get.return_value.__enter__.return_value
            download.iter_content.return_value = iter([b'PK\x03\x04'])
            path = Path(td) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['inventory_features'], 101)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(query.call_count, 3)
            self.assertEqual(query.call_args_list[-1].args[1]['objectIds'], '100')
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_incomplete_batch_does_not_replace_existing_output(self):
        adapter = VillarrubiaDeLosOjosAyuntamientoAdapter('villarrubia-de-los-ojos')
        with tempfile.TemporaryDirectory() as td, patch.object(adapter, '_query', side_effect=[
            {'objectIds': [1104, 1105], 'objectIdFieldName': 'OBJECTID'}, {'features': [feature()]}]):
            path = Path(td) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
