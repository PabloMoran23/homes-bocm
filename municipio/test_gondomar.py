"""Offline parser/contract tests; live evidence is produced separately."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.gondomar import (
    BASE, CLASSES, GondomarAyuntamientoAdapter, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def fixture():
    item = {'id': '28486', 'docnome': 'PEID CENTRO DE DÍA',
            'figura': 'Plan especial de infraestruturas e dotacións',
            'fechaaddef': '2022-06-06', 'fechabop': '2022-12-29',
            'fechadog': '2022-11-25', 'fechanormativabop': '2022-12-29',
            'incidencias_iuris': None}
    general = {**item, 'denominacion': item['docnome'], 'menutitle': 'Gondomar',
               'folder': 'GONDOMAR', 'filesroot': 'documentos/urbanismo/'}
    component = {'id': '128159', 'pathesperado': '28486me001.pdf', 'descripcion': 'MEMORIA'}
    detail = {'datos_xerais': general, 'incidencias_iuris': None,
              'elementos': [{'description': 'MEMORIA', 'componentes': [component, component]},
                            {'description': 'PLANOS', 'componentes': [
                                {'id': '128160', 'pathesperado': '28486pi001.pdf', 'descripcion': 'SITUACIÓN'}]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_groups_documents_and_keeps_date_semantics(self):
        item, detail = fixture()
        row = parse_instrument(item, detail, CLASSES[13])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], BASE + 'documentos/urbanismo/GONDOMAR/documents/28486me001.pdf')
        self.assertEqual(row['fecha_aprob'], '2022-06-06')
        self.assertEqual(row['fecha_publicacion_dog'], '2022-11-25')
        self.assertEqual(row['fecha_publicacion_bop'], '2022-12-29')
        self.assertIsNone(row['fecha'])
        self.assertNotIn('fase', row)
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fecha_concesion', row)
        for key in ['fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop']:
            item[key] = detail['datos_xerais'][key] = None
        row = parse_instrument(item, detail, CLASSES[13])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion_dog'])

    def test_explicit_null_document_inventory_is_preserved(self):
        item, detail = fixture()
        detail['elementos'] = None
        row = parse_instrument(item, detail, CLASSES[13])
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentos_status'], 'not_exposed_by_source')

    def test_entire_inventory_not_first_display_page(self):
        item, _ = fixture()
        payload = [{**item, 'id': str(n)} for n in range(150)]
        self.assertEqual(len(parse_inventory(payload)), 150)
        self.assertEqual(len(parse_inventory([item, item])), 1)
        self.assertEqual(parse_inventory(None), [])
        for bad in [{'data': payload, 'next': 2}, 'Forbidden', [{}],
                    [item, {**item, 'docnome': 'conflicting title'}]]:
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_rejects_cross_municipality_missing_documents_and_changed_dates(self):
        item, detail = fixture()
        cases = []
        for key, value in [('id', '1'), ('menutitle', 'Gondomar Portugal'),
                           ('fechaaddef', '2022-01-01'), ('filesroot', 'https://example.com/')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][key] = value
            cases.append(changed)
        cases.append({**detail, 'elementos': {}})
        changed = copy.deepcopy(detail)
        changed['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        cases.append(changed)
        for changed in cases:
            with self.assertRaises(ValueError):
                parse_instrument(item, changed, CLASSES[13])
        item['fechaaddef'] = detail['datos_xerais']['fechaaddef'] = '2022-02-30'
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, CLASSES[13])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('gondomar')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('36021', 'Pontevedra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = GondomarAyuntamientoAdapter('gondomar')
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session') as session:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
            session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
