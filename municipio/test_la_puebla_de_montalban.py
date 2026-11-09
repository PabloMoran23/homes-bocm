import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.la_puebla_de_montalban import (
    BASE, LaPueblaDeMontalbanAyuntamientoAdapter, parse_projects,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def post(identifier, title, body, published='2023-05-20T09:37:17'):
    return {'id': identifier, 'link': f'{BASE}/documento-{identifier}.html',
            'title': {'rendered': title}, 'content': {'rendered': body}, 'date': published}


def approval():
    return post(1, 'APROBACIÓN DEL PLAN DE ORDENACIÓN MUNICIPAL',
                '<p>Publicado en DOCM el 09/05/2023. El Pleno del Ayuntamiento HA APROBADO '
                'el Plan de Ordenación Municipal en Pleno Extraordinario celebrado el viernes 19/05/2023.</p>'
                '<p>Se remitirá a la Consejería a los efectos de su aprobación definitiva.</p>')


def consultation():
    return post(2, 'INFORMACIÓN PÚBLICA DEL PLAN DE ORDENACIÓN MUNICIPAL',
                '<p>Se inicia el período de información pública. El documento del POM está disponible '
                '<a href="https://lapueblademontalban.sedelectronica.es/">en sede</a>.</p>', '2020-03-05T09:10:05')


class ParserTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        row, = parse_projects([consultation(), approval(), consultation()])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2023-05-19')
        self.assertEqual(row['fecha_publicacion'], '2023-05-20')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['enlaces'], ['https://lapueblademontalban.sedelectronica.es/'])

    def test_context_does_not_create_another_project(self):
        context = post(3, 'Reunión con la CHT', '<p>Plan de Ordenación Municipal: '
                       'se solicita informe a CHT para continuar los trámites.</p>', '2024-03-19T14:12:01')
        row, = parse_projects([approval(), context])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_ultima_publicacion_fuente'], '2024-03-19')
        self.assertEqual(row['fecha_acuerdo'], '2023-05-19')

    def test_notices_and_forms_are_not_records(self):
        for title in ['Solicitud de licencia urbanística', 'Firma del contrato de redacción del Plan de Ordenación Municipal', 'Reunión']:
            with self.assertRaises(ValueError):
                parse_projects([post(4, title, '<p>Plan de Ordenación Municipal</p>')])
        with self.assertRaises(ValueError):
            parse_projects([])

    def test_missing_agreement_date_fails(self):
        p = approval()
        p['content']['rendered'] = p['content']['rendered'].replace('19/05/2023', 'ayer')
        with self.assertRaises(ValueError):
            parse_projects([p])

    def test_foreign_source_rejected(self):
        p = approval()
        p['link'] = 'https://example.org/plan'
        with self.assertRaises(ValueError):
            parse_projects([p])

    def test_pagination_and_count_guard(self):
        def response(batch, total='2'):
            r = Mock(url=BASE + '/wp-json/wp/v2/posts', text='[]')
            r.headers = {'X-WP-TotalPages': '2', 'X-WP-Total': total}
            r.json.return_value = batch
            return r
        with patch('municipio.adapters.la_puebla_de_montalban.requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = [response([consultation()]), response([approval()])]
            adapter = LaPueblaDeMontalbanAyuntamientoAdapter('la-puebla-de-montalban')
            posts, urls = adapter.fetch_posts()
            self.assertEqual(len(posts), 2)
            self.assertEqual(len(urls), 2)
            self.assertEqual(client.get.call_args.kwargs['params']['page'], 2)
            client.get.side_effect = [response([consultation()]), response([consultation()])]
            with self.assertRaises(ValueError):
                adapter.fetch_posts()
            client.get.side_effect = [response([consultation()]), response([approval()], '3')]
            with self.assertRaises(ValueError):
                adapter.fetch_posts()

    def test_manifest_loads_and_licences_disabled(self):
        manifest = load_manifest('la-puebla-de-montalban')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
