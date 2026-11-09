"""Offline parser and extraction contract tests; no live website dependency."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.neda import NedaAyuntamientoAdapter, parse_inventory, parse_instrument
from municipio.manifest import load_manifest, load_yaml


def fixture():
    entry = {'id': '123', 'docnome': 'DE REFORMA INTERIOR XUBIA-CASADELOS',
             'figura': 'Plan Especial', 'fechaaddef': '2005-02-18', 'fechabop': '2005-04-02'}
    detail = {'datos_xerais': {'id': '123', 'denominacion': entry['docnome'],
              'figura': 'Plan Especial', 'menutitle': 'Neda', 'folder': 'NEDA',
              'filesroot': 'documentos/urbanismo/', 'fechaaddef': '2005-02-18',
              'fechabop': '2005-04-02'}, 'elementos': [
                  {'description': 'MEMORIA', 'componentes': [
                      {'id': '1', 'descripcion': 'Memoria', 'pathesperado': 'memoria.pdf'},
                      {'id': '2', 'descripcion': 'Plano', 'pathesperado': 'plano.jpg'}]}]}
    return entry, detail


class NedaTests(unittest.TestCase):
    def test_document_grouping_and_dates(self):
        entry, detail = fixture()
        row = parse_instrument(entry, detail, {13})
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob'], '2005-02-18')
        self.assertEqual(row['fecha_publicacion_bop'], '2005-04-02')
        self.assertTrue(row['documentos'][0]['url'].endswith('/NEDA/documents/memoria.pdf'))
        for field in ['fecha', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, row)

    def test_history_and_missing_documents(self):
        entry, detail = fixture()
        detail['elementos'] = None
        row = parse_instrument(entry, detail, {16})
        self.assertTrue(row['historico'])
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentacion_status'], 'sin_documentos_disponibles')

    def test_schema_drift_and_pagination_fail(self):
        self.assertEqual(parse_inventory(None), [])
        for payload in [{'results': [], 'next': 2}, [{'id': '1', 'docnome': 'Formulario'}], '<html>error</html>']:
            with self.assertRaises(ValueError):
                parse_inventory(payload)

    def test_cross_municipality_identity_dates_and_document_paths(self):
        entry, detail = fixture()
        for field, value in [('menutitle', 'Narón'), ('id', '456'), ('fechaaddef', '2005-03-01')]:
            other = copy.deepcopy(detail)
            other['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_instrument(entry, other, {13})
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../other.pdf'
        with self.assertRaises(ValueError):
            parse_instrument(entry, detail, {13})

    def test_full_extraction_merges_duplicate_instruments_and_reads_all_classes(self):
        entry, detail = fixture()
        response = Mock(url='https://siotuga.xunta.gal/siotuga/inventario', content=b'<input id="token" value="public-form-token"><select id="idconcello"><option value="15055">Neda</option></select>')
        session = Mock(headers={})
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.get.return_value = response
        def result(payload):
            r = Mock()
            r.json.return_value = payload
            return r
        session.post.side_effect = [result([entry]), result([entry]), result(None), result(None), result(detail)]
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.neda.requests.Session', return_value=session):
            out = Path(directory) / 'projects.jsonl'
            adapter = NedaAyuntamientoAdapter('neda')
            report = adapter.backfill_proyectos(out)
            self.assertEqual(report['count'], 1)
            self.assertEqual(session.post.call_count, 5)
            row = json.loads(out.read_text())
            self.assertEqual(len(row['categorias_inventario']), 2)
            self.assertEqual(len(row['documentos']), 2)
            # A partial failure must not overwrite the last complete output.
            previous = out.read_bytes()
            session.post.side_effect = [result([entry]), result({'results': [], 'next': 2})]
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)

    def test_manifest(self):
        manifest = load_manifest('neda')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15055')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
