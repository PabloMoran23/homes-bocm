"""Offline parser/contract tests; fixtures model the public SIOTUGA JSON shape."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.meano import (CLASSES, MeanoAyuntamientoAdapter,
                                      parse_inventory, parse_project)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    row = {'id': '28621', 'docnome': 'PEID TANATORIO DE MEAÑO',
           'figura': 'Plan especial de infraestruturas e dotacións',
           'fechaaddef': '2023-03-31', 'fechabop': '2023-12-07',
           'fechadog': '2023-05-19', 'fechanormativabop': '2023-12-07',
           'incidencias_iuris': None}
    general = {**row, 'denominacion': row['docnome'], 'menutitle': 'Meaño',
               'folder': 'MEANO', 'filesroot': 'documentos/urbanismo/'}
    detail = {'datos_xerais': general, 'elementos': [
        {'description': 'MEMORIA', 'componentes': [
            {'id': '132208', 'pathesperado': '28621mx001.pdf', 'descripcion': 'MEMORIA INFORMATIVA'}]},
        {'description': 'PLANOS', 'componentes': [
            {'id': '132234', 'pathesperado': '28621pord001.pdf', 'descripcion': 'ORDENACIÓN'}]}]}
    return row, detail


class MeanoTests(unittest.TestCase):
    def test_group_and_date_semantics(self):
        row, detail = fixture()
        result = parse_project(row, detail, CLASSES[13])
        self.assertEqual(len(result['documentos']), 2)
        self.assertEqual(result['fecha_aprob'], '2023-03-31')
        self.assertEqual(result['fecha_publicacion_dog'], '2023-05-19')
        self.assertEqual(result['fecha_publicacion_bop'], '2023-12-07')
        self.assertIsNone(result['fecha_publicacion'])
        self.assertIsNone(result['lat'])
        self.assertEqual(result['codigo_ine'], '36027')
        self.assertTrue(result['documentos'][0]['url'].endswith('/MEANO/documents/28621mx001.pdf'))

    def test_missing_dates_and_legal_incidence_retained(self):
        row, detail = fixture()
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            row[field] = detail['datos_xerais'][field] = None
        row['incidencias_iuris'] = 'APROBACION DEFINITIVA POR SILENCIO ADMINISTRATIVO.'
        result = parse_project(row, detail, CLASSES[13])
        self.assertIsNone(result['fecha_aprob'])
        self.assertIsNone(result['fase'])
        self.assertEqual(result['incidencias_juridicas'], row['incidencias_iuris'])

    def test_no_silent_pagination_or_invalid_inventory(self):
        row, _ = fixture()
        self.assertEqual(parse_inventory([row, row]), [row])
        self.assertEqual(parse_inventory(None), [])
        for invalid in ({'results': [row], 'next': '?page=2'}, '<html>Login</html>', [{}],
                        [row, {**row, 'docnome': 'Conflicting title'}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_inventory(invalid)
        many = [{**row, 'id': str(i)} for i in range(200)]
        self.assertEqual(len(parse_inventory(many)), 200)

    def test_reject_wrong_place_mismatch_and_empty_documents(self):
        row, original = fixture()
        for field, value in [('menutitle', 'Meis'), ('id', '999'), ('fechaaddef', '2024-01-01')]:
            detail = copy.deepcopy(original)
            detail['datos_xerais'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_project(row, detail, CLASSES[13])
        original['elementos'] = []
        with self.assertRaises(ValueError):
            parse_project(row, original, CLASSES[13])

    def test_live_failure_keeps_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'projects.jsonl'
            target.write_text('previous snapshot\n')
            with patch('municipio.adapters.meano.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    MeanoAyuntamientoAdapter('meano').backfill_proyectos(target)
            self.assertEqual(target.read_text(), 'previous snapshot\n')

    def test_manifest_loading_and_licences_disabled(self):
        manifest = load_manifest('meano')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), MeanoAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'licencias.jsonl'
            result = MeanoAyuntamientoAdapter('meano').backfill_licencias(target)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
