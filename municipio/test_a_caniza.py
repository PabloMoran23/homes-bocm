"""Source-shaped fixtures; no live network or local evidence required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.a_caniza import (
    ACanizaAyuntamientoAdapter, CLASSES, DETAIL, INVENTORY, QUERY,
    parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture(key='22807', title='PLAN XERAL DE ORDENACIÓN MUNICIPAL'):
    item = {'id': key, 'docnome': title, 'figura': 'Plan Xeral de Ordenación Municipal',
            'fechaaddef': '2003-06-27', 'fechabop': '2003-08-29',
            'fechadog': '2003-08-25', 'fechanormativabop': '2003-08-29'}
    meta = {**item, 'denominacion': title, 'menutitle': 'Cañiza, A',
            'folder': 'ACANIZA', 'filesroot': 'documentos/urbanismo/'}
    component = {'id': '51424', 'pathesperado': '0764me002.pdf', 'descripcion': 'MEMORIA'}
    detail = {'datos_xerais': meta, 'incidencias_iuris': None,
              'elementos': [{'description': 'MEMORIA', 'componentes': [component, component]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        item, detail = fixture()
        row = parse_instrument(item, detail, 14)
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(len(row['documentos'][0]['referencias']), 1)
        self.assertEqual(row['fecha_aprob'], '2003-06-27')
        self.assertEqual(row['fecha_publicacion_dog'], '2003-08-25')
        self.assertEqual(row['fecha_publicacion_bop'], '2003-08-29')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['source_id'], '22807')
        self.assertTrue(row['documentos'][0]['url'].endswith('/ACANIZA/documents/0764me002.pdf'))
        other, other_detail = fixture('22808', 'NSP NUM 1')
        other_detail['elementos'][0]['componentes'] = [
            {'id': '1', 'pathesperado': 'another.pdf', 'descripcion': 'Other'}]
        second = parse_instrument(other, other_detail, 16)
        self.assertTrue(second['historico'])
        self.assertNotEqual(row['id'], second['id'])
        self.assertNotEqual(row['documentos'], second['documentos'])

    def test_complete_inventory_and_schema_guards(self):
        item, detail = fixture()
        self.assertEqual(parse_inventory([item, item]), [item])
        self.assertEqual(parse_inventory(None), [])
        for bad in ({'data': [item], 'next': 2}, [{'id': '3', 'docnome': 'Licence form'}], [item, {**item, 'docnome': 'conflict'}]):
            with self.assertRaises(ValueError):
                parse_inventory(bad)
        for field, value in [('folder', 'OTHER'), ('id', '9'), ('fechaaddef', '2003-02-30'),
                             ('denominacion', 'Wrong title')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(item, changed, 14)
        for bad_elements in (None, [], [{'description': 'x', 'componentes': None}],
                             [{'description': 'x', 'componentes': [{'pathesperado': '../other.pdf'}]}]):
            with self.assertRaises(ValueError):
                parse_instrument(item, {**detail, 'elementos': bad_elements}, 14)

    def test_full_traversal_and_failure_keeps_previous_snapshot(self):
        item, detail = fixture()
        calls = []

        class Response:
            encoding = 'utf-8'
            text = '<select><option value="36009">Cañiza, A</option></select><input id="token" value="public-form">'
            def __init__(self, payload=None):
                self.payload = payload
            def raise_for_status(self):
                pass
            def json(self):
                return self.payload

        class Session:
            headers = {}
            broken = False
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def request(self, method, url, data=None, timeout=None):
                calls.append((url, data))
                if url == INVENTORY:
                    return Response()
                if url == QUERY:
                    return Response([item] if data['idclase'] == 14 else None)
                if url == DETAIL:
                    return Response(None if self.broken else detail)
                raise AssertionError(url)

        session = Session()
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.a_caniza.requests.Session', return_value=session), patch('municipio.adapters.a_caniza.time.sleep'):
            path = Path(tmp) / 'projects.jsonl'
            adapter = ACanizaAyuntamientoAdapter('a-caniza')
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 1)
            self.assertEqual([data['idclase'] for url, data in calls if url == QUERY], list(CLASSES))
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '36009')
            before = path.read_bytes()
            session.broken = True
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / 'unused-state')
            self.assertEqual(path.read_bytes(), before)
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')

    def test_manifest_loads_through_registry(self):
        manifest = load_manifest('a-caniza')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), ACanizaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
