import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from municipio.adapters.fuente_de_cantos import (
    API, BASE, FuenteDeCantosAyuntamientoAdapter, parse_posts,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def post(number=1, year=2021, identifier=4929):
    return {'id': identifier, 'link': BASE + f'/2021/09/21/anuncio-{identifier}/',
            'date': '2021-09-21T14:02:54',
            'title': {'rendered': f'ANUNCIO-Modificación puntual Nº {number:02}/{year} de las Normas Subsidiarias Municipales'},
            'content': {'rendered': '<p>Se convoca trámite de información pública por 45 días.</p>'
                        '<a href="/wp-content/uploads/memoria.pdf">Memoria y anexos</a>'
                        '<a href="/wp-content/uploads/plano.pdf">Plano 1</a>'}}


def response(batch, pages, total):
    result = MagicMock()
    result.url = API + '?page=1'
    result.headers = {'X-WP-TotalPages': str(pages), 'X-WP-Total': str(total)}
    result.json.return_value = batch
    result.text = json.dumps(batch)
    return result


class ParserTests(unittest.TestCase):
    def test_instrument_and_semantics(self):
        row, = parse_posts([post()])
        self.assertEqual(row['codigo_ine'], '06052')
        self.assertEqual(row['fecha_publicacion'], '2021-09-21')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['publicaciones'][0]['tramite'], 'información pública')
        for field in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)
        self.assertFalse(row['publication_ready'])

    def test_reject_forms_procurement_and_unrelated_posts(self):
        posts = []
        for title in ('Solicitud de licencia de obras', 'Licitación de obras del mercado',
                      'Modificación de relación de puestos de trabajo',
                      'Tasa por licencias urbanísticas', 'Premio de pintura'):
            item = post()
            item['title']['rendered'] = title
            posts.append(item)
        self.assertEqual(parse_posts(posts), [])

    def test_group_documents_and_keep_publication_provenance(self):
        second = post(identifier=5000)
        second['date'] = '2021-10-01T10:00:00'
        second['content']['rendered'] = '<a href="/wp-content/uploads/ambiental.pdf">Documento ambiental</a>'
        rows = parse_posts([post(), second, post(number=2, identifier=6000)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(len(rows[0]['publicaciones']), 2)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_publicacion'], '2021-09-21')

    def test_no_documents_fails(self):
        item = post()
        item['content']['rendered'] = '<a href="https://example.org/fake.pdf">Memoria</a>'
        with self.assertRaises(ValueError):
            parse_posts([item])

    def test_official_origin_required(self):
        item = post()
        item['link'] = 'https://example.org/post/'
        with self.assertRaises(ValueError):
            parse_posts([item])

    @patch('municipio.adapters.fuente_de_cantos.requests.Session')
    def test_all_pages_and_live_output_contract(self, factory):
        session = factory.return_value.__enter__.return_value
        session.get.side_effect = [response([post()], 2, 2),
                                   response([post(number=2, identifier=5000)], 2, 2)]
        adapter = FuenteDeCantosAyuntamientoAdapter('fuente-de-cantos')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            self.assertEqual(len(output.read_text().splitlines()), 2)
        self.assertEqual([c.kwargs['params']['page'] for c in session.get.call_args_list], [1, 2])

    @patch('municipio.adapters.fuente_de_cantos.requests.Session')
    def test_pagination_failure_preserves_previous_output(self, factory):
        session = factory.return_value.__enter__.return_value
        adapter = FuenteDeCantosAyuntamientoAdapter('fuente-de-cantos')
        cases = ([response([post()], 2, 2), response([], 2, 2)],
                 [response([post()], 2, 2), response([post()], 2, 2)],
                 [response([post()], 2, 2), response([post(identifier=5000)], 3, 3)],
                 [response([], 0, 0)])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous extraction\n')
            for responses in cases:
                session.get.side_effect = responses
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), 'previous extraction\n')

    def test_manifest_loads_and_licences_disabled(self):
        manifest = load_manifest('fuente-de-cantos')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, FuenteDeCantosAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
