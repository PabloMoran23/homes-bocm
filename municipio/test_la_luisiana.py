import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.la_luisiana import (
    GROUPS, PREFIX, SOURCE, LaLuisianaAyuntamientoAdapter, page_url, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture(page=1):
    sections = []
    for group, folder in GROUPS.items():
        name = f'plano-{page}' if group == 'PLANOS ESTUDIO DE INUNDABILIDAD' else 'memoria'
        sections.append(f'''<section class="gallery"><h4 class="gallery-title">{group}</h4>
        <table><tbody><tr><td><a href="{PREFIX}{folder}/{name}.PDF">{name}</a></td></tr></tbody></table>
        <ul class="pagination"><li><a href="?pagegalleryfiles-4-1=1#galleryfiles-4-1">1</a></li>
        <li><a href="?pagegalleryfiles-4-1=2#galleryfiles-4-1">2</a></li></ul></section>''')
    return ('<h3>PLAN GENERAL DE ORDENACIÓN URBANA DE LA LUISIANA</h3>' + ''.join(sections) +
            f'<section class="gallery"><h4 class="gallery-title">PROYECTOS DE ACTUACIÓN</h4>'
            f'<table><tbody><a href="{PREFIX}PLANES-DE-ACTUACION/otra.pdf">Otro</a></tbody></table></section>'
            '<a href="/licencia.pdf">Solicitud de licencia</a>')


def response(url, page):
    result = Mock(url=url, text=fixture(page))
    result.raise_for_status.return_value = None
    return result


class LaLuisianaTests(unittest.TestCase):
    def test_documents_scoped_to_pgou(self):
        docs, pages = parse_inventory(fixture())
        self.assertEqual(len(docs), 4)
        self.assertEqual(set(d['grupo'] for d in docs), set(GROUPS))
        self.assertEqual(pages, [SOURCE, SOURCE + '?pagegalleryfiles-4-1=2'])
        self.assertTrue(all('otra.pdf' not in d['url'] for d in docs))

    def test_missing_or_empty_inventory_fails(self):
        for html in ('<h1>Portal</h1>', fixture().replace('PGOU</h4>', 'Otro</h4>'),
                     fixture().replace('<tbody>', '<tbody hidden>').replace('href=', 'data-href=')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_foreign_documents_and_pagination(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace(f'href="{PREFIX}PGOU/', 'href="https://other.test/'))
        for url in ('https://other.test/?pagegalleryfiles-4-1=2', SOURCE + '?offset=2'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                page_url(url)

    @patch('municipio.adapters.la_luisiana.requests.Session')
    def test_live_contract_pagination_grouping_and_semantics(self, factory):
        session = factory.return_value.__enter__.return_value
        session.get.side_effect = [response(SOURCE, 1), response(SOURCE + '?pagegalleryfiles-4-1=2', 2)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            adapter = load_portal_adapter(load_manifest('la-luisiana'))
            result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(session.get.call_count, 2)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['codigo_ine'], '41056')
            self.assertEqual(len(row['documentos']), 5)
            self.assertEqual(len(row['documentos'][0]['inventory_urls']), 2)
            for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)
            self.assertFalse(row['publication_ready'])

    @patch('municipio.adapters.la_luisiana.requests.Session')
    def test_page_failure_does_not_replace_existing_output(self, factory):
        session = factory.return_value.__enter__.return_value
        session.get.side_effect = [response(SOURCE, 1), RuntimeError('unavailable second page')]
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('previous successful extraction')
            with self.assertRaises(RuntimeError):
                LaLuisianaAyuntamientoAdapter('la-luisiana').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous successful extraction')

    def test_licences_disabled(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(LaLuisianaAyuntamientoAdapter('la-luisiana').backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
