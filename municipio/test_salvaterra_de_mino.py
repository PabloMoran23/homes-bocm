"""Offline parser/contract tests; small synthetic fixtures, never live records."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.salvaterra_de_mino import (
    SalvaterraDeMinoAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml


class SalvaterraParserTests(unittest.TestCase):
    def setUp(self):
        self.summary = {'id': '22965', 'docnome': 'NORMAS SUBSIDIARIAS DE PLANEAMENTO',
                        'figura': 'Normas Subsidiarias de Planeamento',
                        'fechaaddef': '1993-06-12', 'fechabop': '1993-07-26',
                        'fechadog': None, 'fechanormativabop': '1993-07-26'}
        general = {**self.summary, 'denominacion': self.summary['docnome'],
                   'menutitle': 'Salvaterra de Miño', 'filesroot': 'documentos/urbanismo/',
                   'folder': 'SALVATERRADEMINO', 'fechatextodef': '1994-07-06'}
        component = {'pathesperado': '0922me001.pdf', 'id': '53295', 'descripcion': 'MEMORIA'}
        self.detail = {'datos_xerais': general, 'elementos': [
            {'description': 'MEMORIA', 'componentes': [component, copy.deepcopy(component)]},
            {'description': 'ANEXO', 'componentes': [copy.deepcopy(component)]}]}

    def parse(self):
        return parse_project(self.summary, self.detail, 14)

    def test_dates_and_grouped_documents(self):
        row = self.parse()
        self.assertEqual(row['fecha_aprob'], '1993-06-12')
        self.assertEqual(row['fecha_publicacion_bop'], '1993-07-26')
        self.assertIsNone(row['fecha_publicacion_dog'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['secciones'], ['MEMORIA', 'ANEXO'])
        self.assertEqual(row['documentos'][0]['url'],
                         'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/SALVATERRADEMINO/documents/0922me001.pdf')
        self.assertEqual(row['codigo_ine'], '36050')
        self.assertFalse(row['publication_ready'])
        self.assertIsNone(row['geometry'])

    def test_missing_documents_and_dates_preserved(self):
        self.detail['elementos'] = None
        for field in ('fechaaddef', 'fechabop', 'fechanormativabop'):
            self.summary[field] = self.detail['datos_xerais'][field] = None
        row = self.parse()
        self.assertEqual(row['documentos'], [])
        self.assertTrue(row['quality_warnings'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['fecha_aprob'])

    def test_bad_chronology_retained_and_flagged(self):
        self.summary['fechadog'] = self.detail['datos_xerais']['fechadog'] = '1992-01-01'
        row = self.parse()
        self.assertEqual(row['fecha_publicacion_dog'], '1992-01-01')
        self.assertEqual(len(row['quality_warnings']), 1)

    def test_identity_and_municipality_guard(self):
        for field, value in [('id', '999'), ('menutitle', 'Otro municipio')]:
            with self.subTest(field=field):
                original = self.detail['datos_xerais'][field]
                self.detail['datos_xerais'][field] = value
                with self.assertRaises(ValueError):
                    self.parse()
                self.detail['datos_xerais'][field] = original

    def test_inventory_detail_mismatch(self):
        self.detail['datos_xerais']['fechaaddef'] = '1994-01-01'
        with self.assertRaises(ValueError):
            self.parse()

    def test_invalid_date_not_inferred(self):
        self.summary['fechabop'] = self.detail['datos_xerais']['fechabop'] = '1993-02-30'
        with self.assertRaises(ValueError):
            self.parse()

    def test_document_location_guard(self):
        self.detail['datos_xerais']['filesroot'] = 'https://example.org/'
        with self.assertRaises(ValueError):
            self.parse()

    def test_complete_arrays_and_duplicate_identity(self):
        self.assertEqual(parse_inventory(None), [])
        self.assertEqual(len(parse_inventory([self.summary, self.summary])), 1)
        other = {**self.summary, 'docnome': 'Changed'}
        with self.assertRaises(ValueError):
            parse_inventory([self.summary, other])
        # More than a browser page of rows must survive parsing.
        many = [{**self.summary, 'id': str(i)} for i in range(125)]
        self.assertEqual(len(parse_inventory(many)), 125)

    def test_pagination_or_login_schema_rejected(self):
        for payload in ({'results': [self.summary], 'next': '?page=2'}, '<html>login</html>', [{'title': 'Solicitud licencia'}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_disabled_licences_and_snapshot_update(self):
        adapter = SalvaterraDeMinoAyuntamientoAdapter('salvaterra-de-mino')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = adapter.update_licencias(output, Path(tmp) / 'state.json')
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 14}) as refresh:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('state')), {'rows': 14})
            refresh.assert_called_once_with(Path('unused'))

    def test_manifest_schema_and_safety_settings(self):
        manifest = load_manifest('salvaterra-de-mino')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36050')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertTrue(manifest.portal.adapter.endswith(':SalvaterraDeMinoAyuntamientoAdapter'))


if __name__ == '__main__':
    unittest.main()
