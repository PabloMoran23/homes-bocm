"""Offline parser checks; live captures and output live separately under evidence/."""
import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.cervo import CervoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    row = {'id': '28469', 'docnome': 'PEID PARA O ACONDICIONAMENTO DA ESTRADA AS QUINTÁS',
           'figura': 'Plan especial de infraestruturas e dotacións',
           'fechaaddef': '2022-06-03', 'fechabop': '2022-08-05',
           'fechadog': '2022-07-01', 'fechanormativabop': '2022-08-05',
           'incidencias_iuris': 'Advertencia conservada'}
    general = {**row, 'denominacion': row['docnome'], 'folder': 'CERVO',
               'menutitle': 'Cervo', 'filesroot': 'documentos/urbanismo/'}
    component = {'id': '1', 'pathesperado': 'memoria.pdf', 'descripcion': 'Memoria'}
    detail = {'datos_xerais': general, 'incidencias_iuris': None,
              'elementos': [{'description': 'MEMORIA', 'componentes': [component, component.copy(),
                  {'id': '2', 'pathesperado': 'memoria.pdf', 'descripcion': 'Plano incluido en memoria'},
                  {'id': '3', 'pathesperado': 'plano 1.jpg', 'descripcion': 'Plano 1'}]}]}
    return row, detail


class CervoTests(unittest.TestCase):
    def test_group_documents_keep_catalog_labels_and_dates(self):
        row, detail = fixture()
        parsed = Adapter.parse_inventory([row, row.copy()], 13)
        self.assertEqual(len(parsed), 1)
        result = Adapter.parse_detail(parsed[0], detail, 13)
        self.assertEqual(result['id'], 'cervo-siotuga-28469')
        self.assertEqual(result['codigo_ine'], '27013')
        self.assertEqual(len(result['documentos']), 3)
        self.assertTrue(result['documentos'][2]['url'].endswith('plano%201.jpg'))
        self.assertEqual(result['fecha_aprob'], '2022-06-03')
        self.assertEqual(result['fecha_publicacion_dog'], '2022-07-01')
        self.assertEqual(result['fecha_publicacion_bop'], '2022-08-05')
        self.assertIsNone(result['fecha_publicacion'])
        self.assertIsNone(result['fecha_acuerdo'])
        self.assertIsNone(result['geometry'])
        self.assertEqual(result['incidencias_juridicas'], 'Advertencia conservada')
        self.assertEqual(result['provenance']['detail']['parameters']['iddoc'], '28469')

    def test_reject_pagination_envelope_and_unknown_classes(self):
        for payload in [{'data': [], 'next': '?page=2'}, '<html>error</html>', {}]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(payload, 14)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([], 16)
        self.assertEqual(Adapter.parse_inventory(None, 18), [])

    def test_reject_conflicting_ids_and_invalid_dates(self):
        row, _ = fixture()
        other = {**row, 'docnome': 'Otro instrumento'}
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([row, other], 13)
        for value in ['2022-02-30', '03/06/2022']:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory([{**row, 'fechaaddef': value}], 13)

    def test_detail_must_match_municipality_identity_and_dates(self):
        row, detail = fixture()
        for key, value in [('id', '999'), ('folder', 'BURELA'), ('menutitle', 'Burela'),
                           ('fechaaddef', '2022-06-04'), ('denominacion', 'Otro plan'),
                           ('filesroot', 'https://example.org/')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][key] = value
            with self.assertRaises(ValueError, msg=key):
                Adapter.parse_detail(row, changed, 13)

    def test_missing_documents_and_unsafe_paths_fail(self):
        row, detail = fixture()
        for elements in [[], None]:
            parsed = Adapter.parse_detail(row, {**detail, 'elementos': elements}, 13)
            self.assertEqual(parsed['documentos'], [])
            self.assertEqual(parsed['documentos_status'], 'unavailable_in_catalogue')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(row, {**detail, 'elementos': {'next': '?page=2'}}, 13)
        for path in ['../other.pdf', '/other.pdf', 'https://example.org/other.pdf']:
            changed = copy.deepcopy(detail)
            changed['elementos'][0]['componentes'][0]['pathesperado'] = path
            with self.assertRaises(ValueError):
                Adapter.parse_detail(row, changed, 13)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cervo')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Cervo', 'Lugo', '27013'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = Adapter('cervo').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
