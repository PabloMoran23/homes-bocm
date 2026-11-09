"""Offline parser/refresh contract tests; no dependence on local live evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cospeito import (
    CospeitoAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest, load_yaml


def fixture():
    item = {'id': '28671', 'docnome': 'ED RÚA CURROS ENRÍQUEZ PARA DEFINIR ALIÑACIÓNS',
            'figura': 'Estudio de Detalle', 'fechaaddef': '2024-09-26',
            'fechabop': '2024-10-08', 'fechadog': '2024-10-04',
            'fechanormativabop': '2024-10-08'}
    general = {**item, 'denominacion': item['docnome'], 'menutitle': 'Cospeito',
               'folder': 'COSPEITO', 'filesroot': 'documentos/urbanismo/'}
    detail = {'datos_xerais': general, 'incidencias_iuris': [{'descripcion': 'Ámbito excluído'}],
              'elementos': [{'description': 'NORMATIVA', 'componentes': [
                  {'id': '1', 'pathesperado': '28671no001.pdf', 'descripcion': 'Normativa'},
                  {'id': '2', 'pathesperado': '28671pl001.jpg', 'descripcion': 'Plano'}]}]}
    return item, detail


class CospeitoTests(unittest.TestCase):
    def test_identity_dates_grouping_and_legal_limits(self):
        item, detail = fixture()
        detail['elementos'].append(copy.deepcopy(detail['elementos'][0]))
        rows = parse_inventory([item, item])
        self.assertEqual(len(rows), 1)
        record = parse_instrument(rows[0], detail, {13})
        self.assertEqual(record['fecha_aprob'], '2024-09-26')
        self.assertEqual(record['fecha_publicacion_dog'], '2024-10-04')
        self.assertEqual(record['fecha_publicacion_bop'], '2024-10-08')
        self.assertIsNone(record['fecha_publicacion'])
        self.assertEqual(len(record['documentos']), 2)
        self.assertEqual(record['documentos'][0]['url'], 'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/COSPEITO/documents/28671no001.pdf')
        self.assertEqual(record['incidencias_juridicas'], detail['incidencias_iuris'])
        self.assertIsNone(record['geometry'])

    def test_fail_closed_on_schema_pagination_and_bad_details(self):
        self.assertEqual(parse_inventory(None), [])
        for payload in ({'results': [], 'next': '?page=2'}, [{'title': 'Formulario'}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload)
        item, detail = fixture()
        with self.assertRaises(ValueError):
            parse_inventory([item, {**item, 'docnome': 'different'}])
        for field, value in [('menutitle', 'Lugo'), ('id', '123'), ('fechaaddef', '2024-09-27')]:
            bad = copy.deepcopy(detail)
            bad['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(item, bad, {13})
        detail['elementos'] = []
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, {13})

    def test_live_flow_all_classes_and_documents(self):
        item, detail = fixture()
        calls = []
        class Response:
            encoding = 'utf-8'
            def __init__(self, payload=None, html=None):
                self.text = html if html else json.dumps(payload)
            def raise_for_status(self):
                pass
            def json(self):
                return json.loads(self.text)
        class Session:
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def get(self, url, **kwargs):
                return Response(html='<input id="token" value="public-form"><select id="idconcello"><option value="27015">Cospeito</option></select>')
            def post(self, url, data, **kwargs):
                calls.append(data.copy())
                return Response(([item] if data['idclase'] in (13, 16) else None) if 'idclase' in data else detail)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.cospeito.requests.Session', Session), patch('municipio.adapters.cospeito.time.sleep'):
            out = Path(tmp) / 'projects.jsonl'
            adapter = CospeitoAyuntamientoAdapter('cospeito')
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 1)
            row = json.loads(out.read_text())
            self.assertEqual(row['provenance']['inventory_classes'], [13, 16])
            self.assertEqual([c['idclase'] for c in calls if 'idclase' in c], [14, 13, 16, 18])
            self.assertEqual(len([c for c in calls if 'iddoc' in c]), 1)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('cospeito')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('27015', 'Lugo'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
