"""Offline contract tests; run with python -m unittest municipio.test_a_pobra_do_caraminal."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.a_pobra_do_caraminal import APobraDoCaraminalAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    item = {'id': '42', 'docnome': 'PLAN PARCIAL', 'figura': 'Plan Parcial',
            'fechaaddef': '2011-10-18', 'fechadog': '2012-01-01', 'fechabop': None,
            'fechanormativabop': None, 'incidencias_iuris': None}
    detail = {'datos_xerais': {'id': '42', 'denominacion': 'PLAN PARCIAL',
                              'menutitle': 'Pobra do Caramiñal, A',
                              'filesroot': 'documentos/urbanismo/', 'folder': 'POBRADOCARAMINAL'},
              'elementos': [{'description': 'MEMORIA', 'componentes': [
                  {'pathesperado': '42me.pdf', 'descripcion': 'Memoria'},
                  {'pathesperado': '42pl.jpg', 'descripcion': 'Plano'}]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_groups_documents_and_preserves_dates(self):
        item, detail = fixture()
        row = Adapter.parse_project(item, detail, 13)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2011-10-18')
        self.assertEqual(row['fecha_publicacion_dog'], '2012-01-01')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])
        self.assertEqual(row['codigo_ine'], '15067')

    def test_conditional_approval_does_not_become_final_date(self):
        item, detail = fixture()
        item['incidencias_iuris'] = 'PRIMEIRA APROBACION PARCIAL; FINAL 03/07/2008'
        row = Adapter.parse_project(item, detail, 14)
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['fechas_fuente']['fechaaddef'], '2011-10-18')
        self.assertEqual(row['incidencias_juridicas'], item['incidencias_iuris'])

    def test_explicit_missing_attachments_retains_verified_instrument(self):
        item, detail = fixture()
        detail['elementos'] = None
        row = Adapter.parse_project(item, detail, 13)
        self.assertEqual(row['documentos'], [])
        self.assertIn('No attachments', row['documentos_status'])

    def test_pagination_or_error_envelope_rejected(self):
        for data in ({'results': [], 'next': 'page2'}, {'error': 'invalid'}, 'error'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(data)
        self.assertEqual(Adapter.parse_inventory(None), [])

    def test_all_inventory_items_retained_and_duplicates_grouped(self):
        item, _ = fixture()
        items = [dict(item, id=str(i)) for i in range(101)]
        self.assertEqual(len(Adapter.parse_inventory(items)), 101)
        self.assertEqual(len(Adapter.parse_inventory([item, copy.deepcopy(item)])), 1)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([item, dict(item, docnome='OTHER')])

    def test_wrong_municipality_provenance_and_wrong_id_rejected(self):
        for change in ('municipality', 'id', 'host'):
            item, detail = fixture()
            if change == 'municipality':
                detail['datos_xerais']['menutitle'] = 'Boiro'
            elif change == 'id':
                detail['datos_xerais']['id'] = '43'
            else:
                detail['datos_xerais']['filesroot'] = 'https://example.com/'
            with self.assertRaises(ValueError):
                Adapter.parse_project(item, detail, 13)

    def test_manifest_loads_adapter_and_disables_licences(self):
        manifest = load_manifest('a-pobra-do-caraminal')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            with patch('requests.Session', side_effect=AssertionError('network forbidden')):
                self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_refresh_writes_complete_snapshot(self):
        adapter = Adapter('a-pobra-do-caraminal')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter._write(out, [{'id': 'old'}])
            adapter._write(out, [{'id': 'new'}, {'id': 'new2'}])
            self.assertEqual([json.loads(s)['id'] for s in out.read_text().splitlines()], ['new', 'new2'])


if __name__ == '__main__':
    unittest.main()
