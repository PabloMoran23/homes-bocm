"""Offline semantic, completeness and adapter contract tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.valsequillo_de_gran_canaria import (
    API, DATASET, ValsequilloDeGranCanariaAyuntamientoAdapter,
    parse_document_index, parse_inventory,
)


def package():
    name = ('Aprobación Definitiva de Corrección de Errores de Plan General de '
            'Ordenación Número 1 de Valsequillo publicado el 20/04/2007 en el '
            'BOC 079/07 y el 19/02/2007 en el BOP 023/07 por Pleno COTMAC el 20/12/2006')
    urls = [('HTML', 'http://geobdp.grafcan.es/core/documentos/1132/'),
            ('PDF', 'https://www.idecanarias.es/resources/CEPGO_N1/indice.html'),
            ('SIPU', 'https://opendata.sitcan.es/download/example.zip')]
    return {'success': True, 'result': {
        'name': DATASET, 'private': False, 'state': 'active',
        'metadata_modified': '2025-10-10T12:46:07', 'num_resources': 3,
        'resources': [{'name': name, 'description': name, 'url': url,
                       'format': fmt, 'state': 'active', 'id': str(i)}
                      for i, (fmt, url) in enumerate(urls)]}}


class PlanningTests(unittest.TestCase):
    def test_group_documents_and_keep_date_semantics(self):
        rows = parse_inventory(package())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], 'valsequillo-plan-1132')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['fecha_acuerdo'], '2006-12-20')
        self.assertEqual([p['fecha'] for p in row['publicaciones']], ['2007-04-20', '2007-02-19'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '35031')

    def test_catalogue_dates_are_not_approval_dates_and_ids_survive_order(self):
        data = package()
        for item in data['result']['resources']:
            item['description'] = item['description'].split(' por Pleno')[0]
        data['result']['resources'].reverse()
        row = parse_inventory(data)[0]
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(row['id'], parse_inventory(package())[0]['id'])

    def test_reject_incomplete_wrong_empty_and_ambiguous_inventories(self):
        for change in ('count', 'municipality', 'empty', 'consultation', 'host', 'form'):
            with self.subTest(change=change):
                data = copy.deepcopy(package())
                p = data['result']
                if change == 'count': p['num_resources'] = 4
                if change == 'municipality': p['name'] = 'another-municipality'
                if change == 'empty': p.update(resources=[], num_resources=0)
                if change == 'consultation': p['resources'][0]['format'] = 'PDF'
                if change == 'host': p['resources'][1]['url'] = 'https://example.com/doc.pdf'
                if change == 'form': p['resources'][1]['name'] = 'Solicitud de licencia de obras'
                with self.assertRaises(ValueError): parse_inventory(data)

    def test_index_relative_urls_duplicates_and_pagination(self):
        url = 'https://www.idecanarias.es/resources/CEPGO_N1/indice.html'
        html = '<a href="TNP/norma.pdf">Norma</a><a href="TNP/norma.pdf">Norma</a>'
        docs = parse_document_index(html, url)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['url'], url.replace('indice.html', 'TNP/norma.pdf'))
        self.assertEqual(docs[0]['procedencia'], url)
        for invalid in ('<p>Sin documentos</p>', html + '<a rel="next" href="page2">2</a>',
                        html + '<a href="otro-indice.html">Más</a>'):
            with self.assertRaises(ValueError): parse_document_index(invalid, url)

    def test_full_refresh_and_no_partial_write_on_failure(self):
        adapter = ValsequilloDeGranCanariaAyuntamientoAdapter('valsequillo-de-gran-canaria')
        class Response:
            content = b'<a href="norma.pdf">Normativa</a>'
            def json(self): return package()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', return_value=Response()):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            row = json.loads(out.read_text())
            self.assertEqual(len(row['documentos']), 4)
            original = out.read_text()
            with patch.object(adapter, '_fetch', side_effect=[Response(), RuntimeError('offline')]):
                with self.assertRaises(RuntimeError): adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
