"""Offline parser contract tests; fixtures model the reviewed SIOTUGA response."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ponte_caldelas import (
    BASE, CLASSES, PonteCaldelasAyuntamientoAdapter, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

ITEM = {'id': '27838', 'docnome': 'DE DOTACIONS DA RUA VALDARROSA',
        'figura': 'Plan Especial', 'fechaaddef': '2013-12-30',
        'fechabop': None, 'fechadog': '2014-02-18', 'fechanormativabop': None}
DETAIL = {'datos_xerais': {**ITEM, 'denominacion': ITEM['docnome'],
                          'menutitle': 'Ponte Caldelas', 'folder': 'PONTECALDELAS',
                          'filesroot': 'documentos/urbanismo/'},
          'elementos': [{'description': 'MEMORIA', 'componentes': [
              {'pathesperado': '27838me001.pdf', 'descripcion': 'MEMORIA'}]},
              {'description': 'NORMATIVA', 'componentes': [
                  {'pathesperado': '27838no001.pdf', 'descripcion': 'ANUNCIO DOG 18/02/2014'}]}]}


class ParserTests(unittest.TestCase):
    def test_group_documents_and_preserve_date_semantics(self):
        detail = copy.deepcopy(DETAIL)
        detail['elementos'].append(detail['elementos'][0])
        row = parse_instrument(ITEM, detail, {13})
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2013-12-30')
        self.assertEqual(row['fecha_publicacion_dog'], '2014-02-18')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['documentos'][0]['url'], BASE + 'documentos/urbanismo/PONTECALDELAS/documents/27838me001.pdf')

    def test_missing_documents_is_explicit(self):
        detail = {**DETAIL, 'elementos': None}
        row = parse_instrument(ITEM, detail, {13})
        self.assertEqual(row['documentos_status'], 'unavailable_in_source')
        self.assertEqual(row['documentos'], [])

    def test_reject_foreign_municipality_and_date_disagreement(self):
        for field, value in [('menutitle', 'Pontevedra'), ('id', '1'), ('fechaaddef', '2014-01-01')]:
            detail = copy.deepcopy(DETAIL)
            detail['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(ITEM, detail, {13})

    def test_inventory_empty_deduplication_and_pagination_envelope(self):
        self.assertEqual(parse_inventory(None), [])
        self.assertEqual(parse_inventory([ITEM, ITEM]), [ITEM])
        for payload in ({'results': [ITEM], 'next': '/page2'}, [ITEM, {**ITEM, 'docnome': 'changed'}], [{}]):
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_full_inventory_walk_and_manifest_resolution(self):
        class Response:
            content = b'<input id="token" value="public-nonce"><select id="idconcello"><option value="36043">Ponte Caldelas</option></select>'
            def __init__(self, payload=None):
                self.payload = payload
            def raise_for_status(self):
                pass
            def json(self):
                return self.payload

        calls = []
        def post(url, data, timeout):
            calls.append(data)
            if 'idclase' in data:
                return Response([ITEM, ITEM] if data['idclase'] == 13 else None)
            return Response(DETAIL)

        manifest = load_manifest('ponte-caldelas')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, PonteCaldelasAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', return_value=Response()), patch('requests.Session.post', side_effect=post):
            result = adapter.backfill_proyectos(Path(tmp) / 'proyectos.jsonl')
            self.assertEqual(result['rows'], 1)
        self.assertEqual([c['idclase'] for c in calls if 'idclase' in c], list(CLASSES))
        self.assertEqual(len([c for c in calls if 'iddoc' in c]), 1)


if __name__ == '__main__':
    unittest.main()
