import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.abegondo import (AbegondoAyuntamientoAdapter, parse_inventory,
                                         parse_instrument)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


class AbegondoParserTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': '28592', 'docnome': 'PLAN XERAL DE ORDENACIÓN MUNICIPAL DE ABEGONDO',
                     'figura': 'Plan Xeral de Ordenación Municipal', 'fechaaddef': '2023-10-19',
                     'fechadog': '2023-11-06', 'incidencias_iuris': None}
        self.detail = {'datos_xerais': {**self.item, 'menutitle': 'Abegondo', 'folder': 'ABEGONDO',
                                       'filesroot': 'documentos/urbanismo/'},
                       'elementos': [{'description': 'Memoria', 'componentes': [
                           {'id': '131095', 'pathesperado': '28592mx001.pdf', 'descripcion': 'INFORMACIÓN'},
                           {'id': '131096', 'pathesperado': '28592mx002.pdf', 'descripcion': 'XUSTIFICACIÓN'}]}]}

    def test_grouping_dates_and_provenance(self):
        rows = [parse_instrument(i, self.detail, 14) for i in parse_inventory([self.item])]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2023-10-19')
        self.assertEqual(row['fecha_publicacion_dog'], '2023-11-06')
        self.assertTrue(row['documentos'][0]['url'].endswith('/ABEGONDO/documents/28592mx001.pdf'))
        self.assertEqual(row['provenance']['detail_parameters']['iddoc'], '28592')
        for field in ['fecha', 'fecha_acuerdo', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, row)

    def test_history_and_missing_dates(self):
        item = {**self.item, 'incidencias_iuris': 'ANULADO POR SENTENCIA', 'fechaaddef': None}
        detail = copy.deepcopy(self.detail)
        detail['datos_xerais']['fechaaddef'] = None
        row = parse_instrument(item, detail, 16)
        self.assertTrue(row['historico'])
        self.assertIn('ANULADO', row['incidencias_juridicas'])
        self.assertNotIn('fecha_aprob', row)

    def test_reject_envelopes_duplicates_and_noninstruments(self):
        for payload in [None, {'data': [self.item], 'next': 2}, [{'titulo': 'Formulario licencia'}], [self.item, self.item]]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_inventory(payload)
        self.assertEqual(parse_inventory([]), [])

    def test_reject_wrong_municipality_and_conflicting_dates(self):
        for key, value in [('menutitle', 'Otro concello'), ('id', '1'), ('fechaaddef', '2023-11-06')]:
            detail = copy.deepcopy(self.detail)
            detail['datos_xerais'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_instrument(self.item, detail, 14)
        detail = {**self.detail, 'elementos': []}
        row = parse_instrument(self.item, detail, 14)
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentos_status'], 'unavailable_in_source')
        detail['elementos'] = None
        self.assertEqual(parse_instrument(self.item, detail, 14)['documentos'], [])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('abegondo')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('15001', 'A Coruña'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), AbegondoAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as temp, patch('requests.Session', side_effect=AssertionError('network')):
            path = Path(temp) / 'licencias.jsonl'
            result = AbegondoAyuntamientoAdapter('abegondo').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
