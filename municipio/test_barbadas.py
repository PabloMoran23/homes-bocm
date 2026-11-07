"""Offline parser/refresh tests using synthetic SIOTUGA-shaped fixtures."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.barbadas import (
    BarbadasAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture():
    item = {'id': '1', 'docnome': 'SECTOR TEST', 'figura': 'Plan Parcial',
            'fechaaddef': '2001-08-08', 'fechadog': '2001-09-17',
            'fechabop': '2001-08-24', 'fechanormativabop': None}
    general = {**item, 'denominacion': item['docnome'], 'menutitle': 'Barbadás',
               'filesroot': 'documentos/urbanismo/', 'folder': 'BARBADAS'}
    detail = {'datos_xerais': general, 'incidencias_iuris': [{'descripcion': 'Test restriction'}],
              'elementos': [{'description': 'NORMATIVA', 'componentes': [
                  {'id': '2', 'pathesperado': 'test.pdf', 'descripcion': 'Normativa'}]},
                  {'description': 'PLANOS', 'componentes': [
                      {'id': '3', 'pathesperado': 'test.jpg', 'descripcion': 'Plano'}]}]}
    return item, detail


class BarbadasTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        item, detail = fixture()
        row = parse_detail(item, detail, 13)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['id'], 'barbadas-plan-1')
        self.assertEqual(row['fecha_aprob'], '2001-08-08')
        self.assertEqual(row['fecha_publicacion_dog'], '2001-09-17')
        self.assertEqual(row['fecha_publicacion_bop'], '2001-08-24')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['incidencias_juridicas'], detail['incidencias_iuris'])
        self.assertEqual(row['documentos'][0]['source_params']['iddoc'], '1')
        self.assertTrue(row['documentos'][0]['url'].endswith('/BARBADAS/documents/test.pdf'))

    def test_missing_dates_stay_missing(self):
        item, detail = fixture()
        for field in ('fechaaddef', 'fechadog', 'fechabop'):
            item[field] = detail['datos_xerais'][field] = None
        row = parse_detail(item, detail, 13)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion_dog'])
        self.assertIsNone(row['fase'])

    def test_reject_wrong_identity_and_changed_dates(self):
        item, detail = fixture()
        for key, value in [('id', '99'), ('folder', 'OURENSE'), ('menutitle', 'Ourense'),
                           ('fechaaddef', '2002-01-01'), ('denominacion', 'Other')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_detail(item, changed, 13)

    def test_reject_invalid_dates(self):
        for value in ('2001-02-30', '08/08/2001', 'yesterday'):
            item, detail = fixture()
            item['fechaaddef'] = detail['datos_xerais']['fechaaddef'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_detail(item, detail, 13)

    def test_documents_required_and_safe(self):
        item, detail = fixture()
        for elements in (None, [], [{'componentes': []}],
                         [{'componentes': [{'pathesperado': '../other.pdf'}]}]):
            with self.subTest(elements=elements), self.assertRaises(ValueError):
                parse_detail(item, {**detail, 'elementos': elements}, 13)

    def test_no_pagination_truncation_or_announcements(self):
        item, _ = fixture()
        self.assertEqual(parse_inventory(None), [])
        many = [{**item, 'id': str(i)} for i in range(150)]
        self.assertEqual(len(parse_inventory(many)), 150)
        for invalid in ({'data': [item], 'next': 'page2'}, '<html>Login</html>',
                        [{'titulo': 'Formulario de licencia'}],
                        [item, {**item, 'docnome': 'Conflict'}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_inventory(invalid)

    def test_refresh_and_failure_preserve_output(self):
        item, detail = fixture()
        html = '<input id="token" value="public-form-token"><select id="idconcello"><option value="32008">Barbadás</option></select>'
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            adapter = BarbadasAyuntamientoAdapter('barbadas')
            with patch.object(adapter, '_fetch', side_effect=[html, json.dumps([item]), json.dumps(detail), 'null']):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            before = path.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[html, '[]', '[]']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_bytes(), before)
            with patch.object(adapter, '_fetch', return_value='<html>Login</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('barbadas')
        adapter = load_portal_adapter(manifest)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '32008')
        self.assertEqual(manifest.provincia, 'Ourense')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
        with self.assertRaises(ValueError):
            BarbadasAyuntamientoAdapter('other')


if __name__ == '__main__':
    unittest.main()
