import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.azkoitia import (
    SOURCE, AzkoitiaAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DETAIL = SOURCE + '/13571-pgou'
ITEM = {'source_id': '13571', 'titulo': 'PGOU - PLAN GENERAL DE ORDENACIÓN URBANA', 'url': DETAIL}
ARTICLE = '''<article class="item-page"><h1>PGOU</h1>
<p>El Pleno Municipal acordó el 19 de diciembre de 2024 dar inicio al procedimiento de aprobación del Plan General de Ordenación Urbana del municipio.</p>
<p>Fases futuras: Aprobación inicial. Aprobación definitiva.</p>
<a href="https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/2025/02/20/c2501012.pdf">Anuncio publicado en el BOG de 20/02/2025.</a>
<a href="/images/programa.pdf">Programa de participación ciudadana.</a>
<a href="/images/programa.pdf">Programa de participación ciudadana.</a></article>'''


def inventory(next_link=''):
    return '''<div class="article-list"><article class="item"><div class="entry-header"><h2>
    <a href="''' + DETAIL + '''">PGOU - PLAN GENERAL DE ORDENACIÓN URBANA</a>
    </h2></div></article><article class="item"><div class="entry-header"><h2>
    <a href="/licencia">Solicitud de licencia de actividad</a></h2></div></article></div>''' + next_link


class AzkoitiaTests(unittest.TestCase):
    def test_dates_and_grouped_documents(self):
        row = parse_project(ARTICLE, ITEM)
        self.assertEqual(row['fecha_acuerdo'], '2024-12-19')
        self.assertEqual(row['fecha_publicacion'], '2025-02-20')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha'])
        self.assertNotIn('fase', row)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['url'], 'https://azkoitia.eus/images/programa.pdf')
        self.assertIsNone(row['geometry'])

    def test_not_a_project_or_missing_provenance(self):
        for html in ('<h1>Login</h1>', ARTICLE.replace('dar inicio al procedimiento', 'aprobar definitivamente'),
                     ARTICLE.replace('Programa de participación ciudadana.', 'Formulario.'),
                     ARTICLE.replace('egoitza.gipuzkoa.eus', 'example.org')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_project(html, ITEM)
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Forbidden</h1>')
        rows, _ = parse_inventory(inventory())
        self.assertEqual(len(rows), 1)

    def test_follow_pagination_and_deduplicate(self):
        page2 = SOURCE + '?start=1'
        first = inventory('<div class="pagination"><a href="?start=1">Siguiente</a></div>')
        calls = []
        def fetch(url):
            calls.append(url)
            return {SOURCE: first, page2: inventory(), DETAIL: ARTICLE}[url]
        adapter = AzkoitiaAyuntamientoAdapter('azkoitia')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(tmp) / 'projects.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(calls, [SOURCE, page2, DETAIL])
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(len(out.read_text().splitlines()), 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'azkoitia-proy-13571')

    def test_unreadable_pagination_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory('Página 1 de 2'))
        with self.assertRaises(ValueError):
            parse_inventory(inventory('<div class="pagination"><a href="https://example.org">Next</a></div>'))

    def test_failed_snapshot_does_not_replace_previous(self):
        adapter = AzkoitiaAyuntamientoAdapter('azkoitia')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), '<h1>Blocked</h1>']), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('azkoitia')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
