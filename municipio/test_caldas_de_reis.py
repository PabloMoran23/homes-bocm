"""Parser/contract tests; synthetic fixtures exercise the observed SIOTUGA schema."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.caldas_de_reis import (
    BASE, INVENTORY, CaldasDeReisAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest, load_yaml


def fixture(key='22776'):
    item = {'id': key, 'docnome': 'NSP NA PARCELA DOS PAIS PASIONISTAS',
            'figura': 'Modificación Puntual', 'fechaaddef': '2000-07-28',
            'fechadog': '2000-09-26', 'fechabop': '2000-09-22',
            'fechanormativabop': None, 'incidencias_iuris': None}
    detail = {'datos_xerais': {'id': key, 'folder': 'CALDASDEREIS',
                              'menutitle': 'Caldas de Reis', 'filesroot': 'documentos/urbanismo/'},
              'elementos': [{'description': 'PLANOS', 'componentes': [
                  {'pathesperado': '0733pl001.jpg', 'descripcion': 'Plano 1'},
                  {'pathesperado': '0733pl002.jpg', 'descripcion': 'Plano 2'}]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        item, detail = fixture()
        detail['elementos'].append(copy.deepcopy(detail['elementos'][0]))
        row = parse_instrument(item, detail, 'planeamiento_general')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2000-07-28')
        self.assertEqual(row['fecha_publicacion_dog'], '2000-09-26')
        self.assertEqual(row['fecha_publicacion_bop'], '2000-09-22')
        self.assertIn('/CALDASDEREIS/documents/0733pl001.jpg', row['documentos'][0]['url'])
        for field in ('fecha', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)

    def test_missing_documents_are_explicit(self):
        item, detail = fixture()
        detail['elementos'] = None
        row = parse_instrument(item, detail, 'planeamiento_desarrollo')
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentos_status'], 'unavailable_in_inventory')

    def test_reject_other_municipality_or_unsafe_document(self):
        item, detail = fixture()
        detail['datos_xerais']['folder'] = 'OTRO'
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, 'test')
        item, detail = fixture()
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        with self.assertRaises(ValueError):
            parse_instrument(item, detail, 'test')

    def test_full_array_or_explicit_empty_only(self):
        self.assertEqual(parse_inventory(None), [])
        items = [fixture(str(i))[0] for i in range(100)]
        self.assertEqual(len(parse_inventory(items)), 100)
        for invalid in ({'results': items, 'next': 'page2'}, '<html>Error</html>', [{}]):
            with self.assertRaises(ValueError):
                parse_inventory(invalid)

    def test_manifest_identity_and_disabled_features(self):
        manifest = load_manifest('caldas-de-reis')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36005')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_live_flow_visits_all_categories_and_details(self):
        class Response:
            url = INVENTORY
            text = '<select><option value="36005">Caldas de Reis</option></select><input id="token" value="anonymous"><input id="lang" value="gl_ES">'
            def raise_for_status(self):
                pass
        class JSONResponse(Response):
            def __init__(self, payload):
                self.payload = payload
                self.text = json.dumps(payload)
            def json(self):
                return self.payload
        calls = []
        def post(url, data, **kwargs):
            calls.append((url, data))
            if 'idclase' in data:
                return JSONResponse([fixture(str(data['idclase']))[0]])
            return JSONResponse(fixture(data['iddoc'])[1])
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session') as session:
            session.return_value.__enter__.return_value.get.return_value = Response()
            session.return_value.__enter__.return_value.post.side_effect = post
            path = Path(directory) / 'proyectos.jsonl'
            result = CaldasDeReisAyuntamientoAdapter('caldas-de-reis').backfill_proyectos(path)
            self.assertEqual(result['live_records'], 4)
            self.assertEqual(len(path.read_text().splitlines()), 4)
            self.assertEqual({data['idclase'] for _, data in calls if 'idclase' in data}, {13, 14, 16, 18})
            self.assertEqual(len(calls), 8)
            # Each instrument gets only its own detail response.
            self.assertEqual(len({json.loads(line)['source_id'] for line in path.read_text().splitlines()}), 4)


if __name__ == '__main__':
    unittest.main()
