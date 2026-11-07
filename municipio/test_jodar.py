import json
import unittest
from unittest.mock import MagicMock, patch

from municipio.adapters.jodar import JodarAyuntamientoAdapter, SOURCE, parse_posts
from municipio.manifest import load_manifest, load_yaml


def publication(ident=1, title='RESTITUCIÓN DE CÉSPED DE CAMPO DE FÚTBOL MUNICIPAL'):
    return {'id': ident, 'link': f'https://www.jodar.es/blog/obra-{ident}/',
            'date': '2026-01-29T14:47:00', 'title': {'rendered': 'Anuncio de financiación'},
            'content': {'rendered': '<p>El Ayuntamiento de Jódar ha recibido una subvención '
                       f'para el proyecto <strong>“{title}”</strong>, '
                       'que supone un 50% del presupuesto de la obra proyectada.</p>'
                       '<a href="https://bop.dipujaen.es/documento.pdf">Documento</a>'}}


class ParserTests(unittest.TestCase):
    def test_named_work_and_date_semantics(self):
        row, = parse_posts([publication()])
        self.assertIn('CÉSPED', row['titulo'])
        self.assertEqual(row['codigo_ine'], '23053')
        self.assertEqual(row['fecha_publicacion'], '2026-01-29')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 2)

    def test_group_same_work_and_isolate_other_work(self):
        rows = parse_posts([publication(), publication(2), publication(3, 'REFORMA DE PLAZA MAYOR')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_exclude_forms_procurement_and_unrelated_subsidy(self):
        for content in ('<p>Solicitud de licencia de obras</p>',
                        '<p>Licitación del contrato de rehabilitación del mercado</p>',
                        '<p>Subvención al Ayuntamiento de Jódar para el empleo</p>'):
            post = publication()
            post['content']['rendered'] = content
            self.assertEqual(parse_posts([post]), [])
        self.assertEqual(parse_posts([publication(title='PROGRAMA DE ACTIVIDADES DEPORTIVAS')]), [])

    def test_foreign_source_rejected(self):
        post = publication()
        post['link'] = 'https://example.org/obra'
        with self.assertRaises(ValueError):
            parse_posts([post])

    def test_manifest(self):
        manifest = load_manifest('jodar')
        self.assertEqual(manifest.provincia, 'Jaén')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '23053')
        for section, field in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][field], False)


class PaginationTests(unittest.TestCase):
    def response(self, posts, total=2, pages=2):
        response = MagicMock()
        response.url = SOURCE
        response.headers = {'X-WP-Total': str(total), 'X-WP-TotalPages': str(pages)}
        response.json.return_value = posts
        response.text = json.dumps(posts)
        return response

    @patch('municipio.adapters.jodar.requests.Session')
    def test_all_pages(self, session):
        get = session.return_value.__enter__.return_value.get
        get.side_effect = [self.response([publication()]), self.response([publication(2)])]
        posts = JodarAyuntamientoAdapter('jodar').fetch_posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual([call.kwargs['params']['page'] for call in get.call_args_list], [1, 2])

    @patch('municipio.adapters.jodar.requests.Session')
    def test_duplicate_or_changed_snapshot_fails(self, session):
        get = session.return_value.__enter__.return_value.get
        get.side_effect = [self.response([publication()]), self.response([publication()])]
        with self.assertRaises(ValueError):
            JodarAyuntamientoAdapter('jodar').fetch_posts()
        get.side_effect = [self.response([publication()]), self.response([publication(2)], total=3)]
        with self.assertRaises(ValueError):
            JodarAyuntamientoAdapter('jodar').fetch_posts()


if __name__ == '__main__':
    unittest.main()
