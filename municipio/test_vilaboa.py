"""Offline parser/contract tests; no network dependency."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vilaboa import (VilaboaAyuntamientoAdapter, group_instruments,
                                        parse_detail, parse_inventory)
from municipio.manifest import load_manifest, load_yaml


def fixture(source_id='28190', title='PLAN XERAL DE ORDENACIÓN MUNICIPAL DO CONCELLO DE VILABOA'):
    row = {'id': source_id, 'docnome': title, 'figura': 'Plan Xeral de Ordenación Municipal',
           'fechaaddef': '2019-02-25', 'fechadog': '2019-03-07', 'fechabop': None,
           'fechanormativabop': None}
    detail = {'datos_xerais': {'id': source_id, 'denominacion': title,
              'figura': row['figura'], 'fechaaddef': row['fechaaddef'],
              'fechadog': row['fechadog'], 'fechabop': None, 'fechanormativabop': None,
              'menutitle': 'Vilaboa', 'folder': 'VILABOA', 'filesroot': 'documentos/urbanismo/'},
              'incidencias_iuris': None,
              'elementos': [{'description': 'NORMATIVA', 'componentes': [
                  {'id': '1', 'pathesperado': source_id + 'no001.pdf', 'descripcion': 'DOG'}]}]}
    return row, detail


class VilaboaTests(unittest.TestCase):
    def test_dates_provenance_and_documents(self):
        row, detail = fixture()
        version = parse_detail(detail, row, 'planeamento_xeral')
        record = group_instruments([version])[0]
        self.assertEqual(record['fecha_aprob'], '2019-02-25')
        self.assertEqual(record['fecha_publicacion_dog'], '2019-03-07')
        self.assertNotIn('fecha_acuerdo', record)
        self.assertNotIn('fecha_publicacion', record)
        self.assertNotIn('lat', record)
        self.assertEqual(record['documentos'][0]['url'],
            'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/VILABOA/documents/28190no001.pdf')
        self.assertEqual(version['provenance']['parameters']['iddoc'], '28190')

    def test_group_partial_approvals_preserving_dates(self):
        row, detail = fixture()
        first = parse_detail(detail, row, 'planeamento_xeral')
        row2, detail2 = fixture('28421', 'APROBACIÓN DEFINITIVA PARCIAL DO PXOM ')
        row2['fechaaddef'] = detail2['datos_xerais']['fechaaddef'] = '2021-10-04'
        row2['fechadog'] = detail2['datos_xerais']['fechadog'] = '2021-10-22'
        second = parse_detail(detail2, row2, 'planeamento_xeral')
        other = copy.deepcopy(first)
        other.update(siotuga_id='27868', figura='Modificación Puntual', titulo='NSP Nº 2')
        records = group_instruments([second, other, first])
        self.assertEqual(len(records), 2)
        plan = next(r for r in records if r['id'].endswith('pxom'))
        self.assertEqual(plan['siotuga_ids'], ['28190', '28421'])
        self.assertEqual(len(plan['documentos']), 2)
        self.assertNotIn('fecha_aprob', plan)
        self.assertEqual(plan['versiones'][1]['fecha_aprob'], '2021-10-04')

    def test_whole_array_no_silent_page_limit(self):
        row, _ = fixture()
        rows = [{**row, 'id': str(i)} for i in range(125)]
        self.assertEqual(len(parse_inventory(rows + [rows[0]])), 125)
        self.assertEqual(parse_inventory(None), [])
        with self.assertRaises(ValueError):
            parse_inventory({'data': rows, 'total': 200})
        with self.assertRaises(ValueError):
            parse_inventory([row, {**row, 'docnome': 'conflict'}])

    def test_reject_invalid_schema_or_dates(self):
        row, _ = fixture()
        for bad in [{'titulo': 'Formulario de licenza'}, {**row, 'fechaaddef': '2019-02'},
                    {**row, 'fechaaddef': '2019-02-30'}]:
            with self.assertRaises(ValueError):
                parse_inventory([bad])

    def test_detail_rejects_mismatch_missing_docs_and_unsafe_paths(self):
        row, detail = fixture()
        for field, value in [('id', '999'), ('menutitle', 'Culleredo'),
                             ('folder', 'OTHER'), ('fechaaddef', '2020-01-01')]:
            bad = copy.deepcopy(detail)
            bad['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_detail(bad, row, 'planeamento_xeral')
        bad = copy.deepcopy(detail)
        bad['elementos'] = []
        with self.assertRaises(ValueError):
            parse_detail(bad, row, 'planeamento_xeral')
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        with self.assertRaises(ValueError):
            parse_detail(detail, row, 'planeamento_xeral')

    def test_disabled_licences_and_update(self):
        adapter = VilaboaAyuntamientoAdapter('vilaboa')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 6}) as mock:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('state')), {'rows': 6})
            mock.assert_called_once()

    def test_manifest(self):
        manifest = load_manifest('vilaboa')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('36058', 'Vilaboa', 'Pontevedra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
