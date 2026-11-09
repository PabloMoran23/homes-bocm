import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.abanilla import AbanillaAyuntamientoAdapter, parse_projects
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def post(n=1, title='Obras en la carretera RM-414', body=None, date='2025-10-01T10:00:00'):
    return {'id': n, 'title': {'rendered': title},
            'content': {'rendered': body or '<p>Visitaron las obras en la RM-414: reciclado del firme con emulsión bituminosa.</p>'},
            'link': f'https://abanilla.es/obra-{n}/', 'date': date}


class ParserTests(unittest.TestCase):
    def test_group_documents_and_publication_semantics(self):
        older = post(body='<p>Visitaron las obras en la RM-414: reciclado del firme con emulsión bituminosa.</p><a href="https://www.carm.es/documento.pdf">Memoria</a>')
        newer = post(2, date='2026-03-05T09:53:28')
        rows = parse_projects([older, newer, older])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-03-05')
        self.assertEqual(rows[0]['documentos'][0]['enlaces'][0]['titulo'], 'Memoria')
        for name in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(rows[0][name])
        self.assertNotIn('fase', rows[0])
        self.assertFalse(rows[0]['publication_ready'])
        self.assertEqual(parse_projects([newer, older])[0]['id'], rows[0]['id'])

    def test_exclude_forms_tenders_and_unrelated_news(self):
        candidates = [post(title='Solicitud de licencia de obras'),
                      post(title='Licitación de carretera RM-414'),
                      post(title='Fomento prevé iniciar obra en carretera'),
                      post(title='Obras de teatro en Abanilla'),
                      post(title='Inspección de maquinaria de obras'),
                      post(title='Obras en carretera RM-414', body='Proyecto anunciado para el futuro en RM-414')]
        self.assertEqual(parse_projects(candidates), [])

    def test_same_road_different_intervention_and_background(self):
        rows = parse_projects([post(), post(2, body='Visitaron las obras en RM-414 para un nuevo puente. Otras inversiones RM-422.')])
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['carretera'] for r in rows}, {'RM-414'})
        self.assertEqual(parse_projects([post(3, title='Estado de obras RM-A21', body='Las obras han consistido en mejora de RM-A21.')])[0]['carretera'], 'RM-A21')

    def test_manifest_and_registry(self):
        manifest = load_manifest('abanilla')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '30001')
        self.assertEqual(manifest.provincia, 'Murcia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), AbanillaAyuntamientoAdapter)

    def test_pagination_is_complete_or_fails(self):
        def response(batch, total=2, pages=2):
            r = Mock()
            r.headers = {'X-WP-Total': str(total), 'X-WP-TotalPages': str(pages)}
            r.url = 'https://abanilla.es/wp-json/wp/v2/posts'
            r.json.return_value = batch
            return r
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            session = Mock()
            session.headers = {}
            with patch('municipio.adapters.abanilla.requests.Session') as factory:
                factory.return_value.__enter__.return_value = session
                session.get.side_effect = [response([post()]), response([post(2)])]
                report = AbanillaAyuntamientoAdapter('abanilla').backfill_proyectos(out)
                self.assertEqual(report['pages'], 2)
                self.assertEqual(report['inventory_posts'], 2)
                self.assertEqual(session.get.call_args_list[1].kwargs['params']['page'], 2)
                self.assertEqual(len(json.loads(out.read_text())['documentos']), 2)
                for responses in ([response([post()]), response([])],
                                  [response([post()]), response([post()])],
                                  [response([post()], total=3), response([post(2)], total=3)],
                                  [response([post()]), response([post(2)], total=3)]):
                    session.get.side_effect = responses
                    with self.assertRaises(ValueError):
                        AbanillaAyuntamientoAdapter('abanilla').backfill_proyectos(out)


if __name__ == '__main__':
    unittest.main()
