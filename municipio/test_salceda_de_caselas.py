import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.salceda_de_caselas import (
    BASE, SOURCE, SalcedaDeCaselasAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest


def fixture():
    item = {'id': '22962', 'docnome': 'NSP NUM 1 DA FICHA DO SAU.04',
            'figura': 'Modificación Puntual', 'fechaaddef': '2000-06-28',
            'fechabop': '2000-08-29', 'fechadog': '2000-09-01',
            'fechanormativabop': None, 'incidencias_iuris': None}
    detail = {'datos_xerais': {**item, 'denominacion': item['docnome'],
              'menutitle': 'Salceda de Caselas', 'folder': 'SALCEDADECASELAS',
              'filesroot': 'documentos/urbanismo/'}, 'incidencias_iuris': None,
              'elementos': [{'description': 'NORMATIVA', 'componentes': [
                  {'id': '16964', 'pathesperado': '0919no001.pdf',
                   'descripcion': 'ANTECEDENTES, MEMORIA, NORMATIVA.'},
                  {'id': '16965', 'pathesperado': '0919pl001.jpg',
                   'descripcion': 'PLANO'}]}]}
    return item, detail


class ParserTests(unittest.TestCase):
    def test_instrument_groups_documents_and_preserves_dates(self):
        item, detail = fixture()
        row = parse_project(item, detail, 14)
        self.assertEqual(row['fecha_aprob'], '2000-06-28')
        self.assertEqual(row['fecha_publicacion_bop'], '2000-08-29')
        self.assertEqual(row['fecha_publicacion_dog'], '2000-09-01')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], BASE + 'documentos/urbanismo/SALCEDADECASELAS/documents/0919no001.pdf')
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])

    def test_missing_dates_and_documents_are_not_invented(self):
        item, detail = fixture()
        for field in ('fechaaddef', 'fechabop', 'fechadog'):
            item[field] = detail['datos_xerais'][field] = None
        detail['elementos'] = None
        row = parse_project(item, detail, 14)
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['cobertura_documental'], 'ficha_sin_adjuntos')

    def test_all_rows_retained_without_page_limit(self):
        item, _ = fixture()
        payload = [{**item, 'id': str(i)} for i in range(125)]
        self.assertEqual(len(parse_inventory(payload)), 125)
        self.assertEqual(parse_inventory(None), [])
        for bad in ({'data': payload, 'next': 2}, '<html>Login</html>', [{'id': 1, 'figura': 'Formulario'}]):
            with self.assertRaises(ValueError):
                parse_inventory(bad)
        with self.assertRaises(ValueError):
            parse_inventory([item, {**item, 'docnome': 'conflict'}])

    def test_wrong_municipality_conflicting_date_and_unsafe_path_fail(self):
        item, detail = fixture()
        for field, value in [('menutitle', 'Porriño'), ('fechaaddef', '2001-01-01'),
                             ('folder', 'OTHER'), ('id', '1')]:
            altered = copy.deepcopy(detail)
            altered['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                parse_project(item, altered, 14)
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../outside.pdf'
        with self.assertRaises(ValueError):
            parse_project(item, detail, 14)

    def test_live_method_reads_all_classes_and_details(self):
        item, detail = fixture()
        class Response:
            url = SOURCE
            text = '<input id="token" value="public-form-value"><option value="36049">Salceda de Caselas</option>'
            def raise_for_status(self): pass
            def json(self): return self.payload
        responses = []
        for payload in ([item], None, None, detail):
            response = Response()
            response.payload = payload
            responses.append(response)
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.salceda_de_caselas.requests.Session') as session:
            session.return_value.__enter__.return_value.get.return_value = Response()
            session.return_value.__enter__.return_value.post.side_effect = responses
            adapter = SalcedaDeCaselasAyuntamientoAdapter('salceda-de-caselas')
            path = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['siotuga_id'], item['id'])
            calls = session.return_value.__enter__.return_value.post.call_args_list
            self.assertEqual([call.kwargs['data']['idclase'] for call in calls[:3]], [14, 13, 18])
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('salceda-de-caselas')
        self.assertEqual(manifest.nombre, 'Salceda de Caselas')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
