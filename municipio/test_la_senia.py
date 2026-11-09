import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_senia import LaSeniaAyuntamientoAdapter as Adapter, agreement_date
from municipio.manifest import load_manifest, load_yaml


def post(pid=1, title='Anunci d’aprovació inicial del projecte d’urbanització dels carrers adjacents a la Pl. Montsià', body=None, published='2025-08-13T13:40:21'):
    return {'id': pid, 'date': published, 'link': f'https://lasenia.cat/web/notice-{pid}/',
            'title': {'rendered': title}, 'content': {'protected': False, 'rendered': body or
            '<p>Aprovat inicialment, mitjançant acord de Ple de data 7 d’agost de 2025.</p><a href="https://lasenia.cat/web/wp-content/uploads/2025/08/projecte.pdf">Projecte</a><a href="https://lasenia.cat/web/wp-content/uploads/2025/08/projecte.pdf">Baixa</a>'}}


class Response:
    def __init__(self, batch, page, total=2, pages=2):
        self.batch = batch
        self.url = f'https://lasenia.cat/web/wp-json/wp/v2/posts?page={page}'
        self.headers = {'X-WP-Total': str(total), 'X-WP-TotalPages': str(pages)}

    def json(self):
        return self.batch

    def raise_for_status(self):
        pass


class LaSeniaTests(unittest.TestCase):
    def test_dates_and_documents(self):
        row = Adapter.parse_projects([post()])[0]
        self.assertEqual(row['fecha_publicacion'], '2025-08-13')
        self.assertEqual(row['fecha_acuerdo'], '2025-08-07')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(agreement_date('Per acord de Ple de data 06/02/2026'), '2026-02-06')
        self.assertEqual(agreement_date('Per Resolució de l’Alcaldia, núm. 2026-0000647, de data 29/05/2026'), '2026-05-29')
        self.assertIsNone(agreement_date('Signat el dia 01/01/2026. Publicat 02/01/2026.'))

    def test_group_initial_final_and_correction(self):
        initial = post()
        final = post(2, 'Anunci d’aprovació definitiva del projecte d’urbanització dels carrers adjacents a la Plaça Montsià', '<p>Per acord de Ple de data 27/10/2025 s’ha aprovat definitivament el projecte.</p>', '2025-11-18T10:00:00')
        correction = post(3, 'Anunci de rectificació d’error material en el Projecte d’urbanització dels carrers adjacents a la Pl. Montsià', published='2025-08-19T10:00:00')
        rows = Adapter.parse_projects([final, initial, correction])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fase'], 'aprobación definitiva')
        self.assertEqual(len(rows[0]['anuncios']), 3)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2025-10-27')
        self.assertEqual(rows[0]['id'], Adapter.parse_projects([initial])[0]['id'])

    def test_excludes_forms_procurement_and_unrelated_projects(self):
        for title in ('Sol·licitud llicència obra Casa de Cultura',
                      'Licitació aprovació del projecte Casa de Cultura',
                      'Projecte joves en pràctiques 2026',
                      'Anunci d’aprovació de l’avantprojecte d’ordenança de subvencions'):
            with self.subTest(title=title), self.assertRaises(ValueError):
                Adapter.parse_projects([post(title=title)])

    def test_pdf_only_has_unknown_agreement_date(self):
        row = Adapter.parse_projects([post(body='<a href="https://lasenia.cat/web/wp-content/uploads/anunci.pdf">Anunci BOPT 02/11/2026</a>')])[0]
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(len(row['documentos']), 1)
        with self.assertRaises(ValueError):
            Adapter.parse_projects([post(body='<p>Inicia sessió</p>')])

    def test_sections_remain_separate(self):
        title = 'Anunci aprovació inicial del projecte executiu de renovació urbanística integral de la sortida nord '
        rows = Adapter.parse_projects([post(title=title + '(Tram Osca-Santander)'), post(2, title + '(Tram Santander-T-1040)')])
        self.assertEqual(len(rows), 2)

    def test_full_pagination_and_update(self):
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.la_senia.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.side_effect = [Response([post()], 1), Response([post(2)], 2)]
            path = Path(directory) / 'projects.jsonl'
            result = Adapter('la-senia').update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['inventory_posts'], 2)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(get.call_args.kwargs['params']['page'], 2)
            self.assertEqual(len(json.loads(path.read_text())['anuncios']), 2)

    def test_bad_pagination_preserves_previous_output(self):
        for responses in ([Response([post()], 1), Response([post()], 2)],
                          [Response([post()], 1), Response([post(2)], 2, total=3)],
                          [Response([post()], 1), Response([], 2)],
                          [Response([post()], 1, total=3, pages=1)]):
            with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.la_senia.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = responses
                path = Path(directory) / 'projects.jsonl'
                path.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    Adapter('la-senia').backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_identity_and_disabled_features(self):
        manifest = load_manifest('la-senia')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('La Sénia', 'Tarragona', '43044'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = Adapter('la-senia').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
