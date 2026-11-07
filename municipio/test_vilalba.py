"""Offline parser contracts; run with python -m unittest municipio.test_vilalba."""
import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.vilalba import select_base_plan, parse_plan, VilalbaAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml


class VilalbaTests(unittest.TestCase):
    def setUp(self):
        self.item = {'id': '28576', 'docnome': 'NORMAS SUBSIDIARIAS DE PLANEAMENTO DE VILALBA',
                     'figura': 'Normas Subsidiarias de Planeamento',
                     'fechaaddef': '1984-03-13', 'fechabop': '1984-04-30',
                     'fechadog': None, 'fechanormativabop': '1984-04-30'}
        self.detail = {
            'datos_xerais': {**self.item, 'denominacion': self.item['docnome'],
                             'menutitle': 'Vilalba', 'filesroot': 'documentos/urbanismo/',
                             'folder': 'VILALBA'},
            'elementos': [{'description': 'MEMORIA XUSTIFICATIVA', 'componentes': [
                {'id': '130618', 'pathesperado': '28576me001.pdf', 'descripcion': 'MEMORIA INFORMATIVA'},
                {'id': '130620', 'pathesperado': '28576me003.pdf', 'descripcion': 'INFORME DE APROBACIÓN'}]}],
            'incidencias_iuris': None,
        }

    def test_dates_and_geometry(self):
        row = parse_plan(self.item, self.detail)
        self.assertEqual(row['fecha_aprob'], '1984-03-13')
        self.assertEqual(row['fecha_publicacion_bop'], '1984-04-30')
        for field in ('fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_publicacion_dog', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_document_grouping_and_stable_identity(self):
        self.detail['elementos'].append(copy.deepcopy(self.detail['elementos'][0]))
        row = parse_plan(self.item, self.detail)
        self.assertEqual(row['id'], 'vilalba-siotuga-28576')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][0]['url'].endswith('/VILALBA/documents/28576me001.pdf'))

    def test_inventory_selection_and_fail_closed(self):
        modification = {**self.item, 'id': '26259', 'figura': 'Modificación Puntual'}
        self.assertEqual(select_base_plan([modification, self.item]), self.item)
        for data in (None, [], {'results': [self.item], 'next': 2}, [self.item, self.item], [modification]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                select_base_plan(data)

    def test_reject_wrong_municipality_mismatch_and_dates(self):
        for key, value in [('menutitle', 'Vilaboa'), ('id', '123'),
                           ('fechaaddef', '2026-01-01'), ('folder', 'VILABOA')]:
            detail = copy.deepcopy(self.detail)
            detail['datos_xerais'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_plan(self.item, detail)

    def test_missing_dates_not_invented(self):
        for key in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            self.item[key] = self.detail['datos_xerais'][key] = None
        row = parse_plan(self.item, self.detail)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_reject_missing_documents_and_escape(self):
        self.detail['elementos'] = []
        with self.assertRaises(ValueError):
            parse_plan(self.item, self.detail)
        self.setUp()
        self.detail['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        with self.assertRaises(ValueError):
            parse_plan(self.item, self.detail)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('vilalba')
        self.assertEqual(manifest.provincia, 'Lugo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '27065')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(VilalbaAyuntamientoAdapter().backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
