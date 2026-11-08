"""Offline parser and adapter contract tests; run with python -m unittest municipio.test_reocin."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.reocin import (
    SOURCE, ReocinAyuntamientoAdapter, parse_inventory,
    parse_document_posts, parse_documents,
)
from municipio.manifest import load_manifest

ROOT = 'https://reocin.wpcomstaging.com'
INVENTORY = '''<main><ul id="menu-menu-urbanismo">
<a href="/plan/">Modificación Puntual NNSS Área 4 La Veguilla</a>
<a href="/plan/">Modificación Puntual NNSS Área 4 La Veguilla</a>
<a href="/licencia/">Solicitud de licencia</a>
<a href="/noticia/">Licitación de piscina</a></ul></main>'''
POSTS = '''<main><h3 class="elementor-post__title"><a href="/memoria/">Memoria</a></h3>
<h3 class="elementor-post__title"><a href="/planos/">Planos</a></h3></main>'''
DOCUMENT = '''<main><h1>Memoria</h1><li itemprop="datePublished"><time>14/08/2024</time></li>
<div class="elementor-widget-theme-post-content"><a href="/uploads/MEMORIA.pdf">Memoria</a>
<a href="/uploads/MEMORIA.pdf">Descargar</a><a href="/contacto/">Contacto</a></div></main>'''


class ReocinTests(unittest.TestCase):
    def test_inventory_deduplicates_and_excludes_forms_and_procurement(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(rows, [{'titulo': 'Modificación Puntual NNSS Área 4 La Veguilla', 'url': ROOT + '/plan/'}])

    def test_posts_and_attachment_publication_date(self):
        self.assertEqual(len(parse_document_posts(POSTS, ROOT + '/plan/')), 2)
        docs = parse_documents(DOCUMENT, ROOT + '/memoria/')
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['fecha_publicacion'], '2024-08-14')
        self.assertNotIn('fecha_acuerdo', docs[0])
        self.assertNotIn('fecha_aprob', docs[0])

    def test_pagination_fails_at_every_inventory_level(self):
        for parser, html, url in [(parse_inventory, INVENTORY, SOURCE),
                                  (parse_document_posts, POSTS, ROOT + '/plan/'),
                                  (parse_documents, DOCUMENT, ROOT + '/memoria/')]:
            for extra in ['<nav class="elementor-pagination"><a href="?page=2">2</a></nav>',
                          '<a rel="next" href="?page=2">→</a>', '<button>Cargar más</button>']:
                with self.subTest(parser=parser.__name__, extra=extra), self.assertRaises(ValueError):
                    parser(html.replace('</main>', extra + '</main>'), url)

    def test_missing_content_and_external_document_fail(self):
        for parser, html, url in [(parse_inventory, '<main></main>', SOURCE),
                                  (parse_document_posts, '<main></main>', ROOT + '/plan/'),
                                  (parse_documents, DOCUMENT.replace('.pdf', '.html'), ROOT + '/memoria/'),
                                  (parse_documents, DOCUMENT.replace('/uploads/', 'https://unrelated.example/'), ROOT + '/memoria/')]:
            with self.subTest(parser=parser.__name__), self.assertRaises(ValueError):
                parser(html, url)

    def test_groups_document_posts_and_does_not_infer_approval(self):
        adapter = ReocinAyuntamientoAdapter('reocin')
        pages = {SOURCE: INVENTORY, ROOT + '/plan/': POSTS,
                 ROOT + '/memoria/': DOCUMENT, ROOT + '/planos/': DOCUMENT,
                 ROOT + '/uploads/MEMORIA.pdf': '%PDF-1.7 test'}

        def fetch(url):
            value = pages[url]
            return SimpleNamespace(url=url, text=value, content=value.encode())

        with tempfile.TemporaryDirectory() as temporary, patch.object(adapter, '_fetch', side_effect=fetch):
            path = Path(temporary) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(rows[0]['documentos']), 1)
            self.assertEqual(len(rows[0]['documentos'][0]['publicaciones']), 2)
            for key in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, rows[0])
            adapter.update_licencias(path, Path(temporary) / 'state.json')
            self.assertEqual(path.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('reocin')
        self.assertEqual(manifest.nombre, 'Reocín')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
