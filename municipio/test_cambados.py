"""Offline contract tests; fixtures represent the observed public JSON schema."""
import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.cambados import (
    CambadosAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml


def fixture():
    item = {'id': '22777', 'docnome': 'NORMAS SUBSIDIARIAS DE PLANEAMENTO',
            'figura': 'Normas Subsidiarias de Planeamento',
            'fechaaddef': '1994-07-20', 'fechabop': None,
            'fechadog': '1995-03-22', 'fechanormativabop': '1995-03-20',
            'incidencias_iuris': 'Texto de incidencia conservado'}
    general = {**item, 'denominacion': item['docnome'], 'menutitle': 'Cambados',
               'filesroot': 'documentos/urbanismo/', 'folder': 'CAMBADOS',
               'fechatextodef': '1995-03-02'}
    detail = {'datos_xerais': general, 'incidencias_iuris': None,
              'elementos': [{'description': 'MEMORIA', 'componentes': [
                  {'id': '50952', 'pathesperado': '0734me011.pdf', 'descripcion': 'MEMORIA DE ORDENACION (1).'},
                  {'id': '50953', 'pathesperado': '0734me012.pdf', 'descripcion': 'MEMORIA DE ORDENACION (2).'}]}]}
    return item, detail


class CambadosTests(unittest.TestCase):
    def test_instrument_groups_documents_and_keeps_date_meaning(self):
        item, detail = fixture()
        row = parse_project(item, detail, 14)
        self.assertEqual(row['id'], 'cambados-siotuga-22777')
        self.assertEqual(row['codigo_ine'], '36006')
        self.assertEqual(row['fecha_aprob'], '1994-07-20')
        self.assertEqual(row['fecha_publicacion_dog'], '1995-03-22')
        self.assertEqual(row['fecha_publicacion_normativa_bop'], '1995-03-20')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][0]['url'].endswith('/CAMBADOS/documents/0734me011.pdf'))
        self.assertEqual(row['incidencias_juridicas'], item['incidencias_iuris'])
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fase', row)

    def test_array_is_complete_and_identifiers_are_deduplicated(self):
        item, _ = fixture()
        self.assertEqual(parse_inventory([item, copy.deepcopy(item)]), [item])
        self.assertEqual(parse_inventory(None), [])
        self.assertEqual(len(parse_inventory([{**item, 'id': str(i)} for i in range(125)])), 125)
        for payload in ({'data': [item], 'next': 2}, [{'titulo': 'Solicitud de licencia'}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload)
        changed = {**item, 'docnome': 'different'}
        with self.assertRaises(ValueError):
            parse_inventory([item, changed])

    def test_fail_closed_on_wrong_municipality_missing_docs_and_changed_dates(self):
        item, detail = fixture()
        for field, value in [('menutitle', 'Cambre'), ('id', '999'),
                             ('folder', 'CAMBRE'), ('fechaaddef', '2020-01-01')]:
            bad = copy.deepcopy(detail)
            bad['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_project(item, bad, 14)
        for elements in (None, []):
            bad = {**detail, 'elementos': elements}
            row = parse_project(item, bad, 14)
            self.assertEqual(row['documentos'], [])
            self.assertEqual(row['document_coverage'], 'no_components_available_in_source')
        bad = copy.deepcopy(detail)
        del bad['elementos']
        with self.assertRaises(ValueError):
            parse_project(item, bad, 14)
        bad = copy.deepcopy(detail)
        bad['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        with self.assertRaises(ValueError):
            parse_project(item, bad, 14)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest(Path(__file__).resolve().parents[1] / 'data/municipios/cambados/manifest.yaml')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36006')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = CambadosAyuntamientoAdapter('cambados').update_licencias(path, Path(tmp) / 'state')
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
