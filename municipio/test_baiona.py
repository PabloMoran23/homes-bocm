import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.baiona import (
    SOURCE, PAGES, BaionaAyuntamientoAdapter, discover_pages, parse_inventories,
)
from municipio.manifest import load_manifest, load_yaml


def fixtures():
    pages = {key: 'https://www.baiona.gal/' + tail + '/' for key, tail in PAGES.items()}
    inventory = '<main>' + ''.join(f'<a href="{u}">{k}</a>' for k, u in pages.items()) + '</main>'
    pdf = 'https://www.baiona.gal/documentacion/urbanismo/a.pdf'
    plan = f'<main><h1>Plan General de Ordenación Municipal</h1><a href="{pdf}">Memoria</a><a href="{pdf}">Planos</a></main>'
    special = '<main><h1>Plan Especial del Conjunto Histórico-Artístico</h1>Área en construcción.</main>'
    def section(title, href):
        return f'<section class="elementor-top-section"><h4 class="wgl-infobox_title">{title}</h4><a href="{href}">{title}</a></section>'
    procedures = '<main>' + section('Licencia Obra Mayor', '/formulario.pdf') + section('PEPCHAB', '/pep.pdf') + section('Normativa PXOM', '/norma.pdf') + '</main>'
    return pages, inventory, {'pxom': plan, 'pepchab': special, 'tramites': procedures}


class BaionaTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        pages, inventory, html = fixtures()
        self.assertEqual(discover_pages(inventory), pages)
        rows = parse_inventories(pages, html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['documentos'][0]['referencias']), 2)
        self.assertEqual(rows[0]['documentos'][0]['referencias'][1]['titulo'], 'Planos')
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertNotIn('formulario', json.dumps(rows))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '36003')
            self.assertNotIn('fecha', row)
            self.assertNotIn('fecha_aprob', row)
            self.assertNotIn('lat', row)
            self.assertEqual(row['geometry_status'], 'unavailable')

    def test_fail_closed_missing_content_pagination_and_navigation(self):
        pages, inventory, html = fixtures()
        with self.assertRaises(ValueError):
            discover_pages('<main>Not an inventory</main>')
        for pagination in ['<a rel="next" href="/p2">2</a>', '<a class="page-numbers" href="/p2">2</a>', '<a href="/p2">Seguinte</a>']:
            with self.assertRaises(ValueError):
                parse_inventories(pages, {**html, 'pxom': html['pxom'].replace('</main>', pagination + '</main>')})
        for broken in ['<main>Unavailable</main>', '<main><h1>Plan general</h1></main>']:
            with self.assertRaises(ValueError):
                parse_inventories(pages, {**html, 'tramites': broken})
        with self.assertRaises(ValueError):
            parse_inventories(pages, {**html, 'pepchab': '<html>Login</html>'})

    def test_refresh_and_failed_fetch_preserves_output(self):
        pages, inventory, html = fixtures()
        sources = {SOURCE: inventory, **{pages[k]: v for k, v in html.items()}}
        adapter = BaionaAyuntamientoAdapter('baiona')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda u: sources[u]):
                result = adapter.update_proyectos(output, Path(folder) / 'state.json')
            self.assertEqual(result['count'], 2)
            original = output.read_text()
            with patch.object(adapter, '_fetch', side_effect=ValueError('HTTP error')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)
            adapter.backfill_licencias(Path(folder) / 'licencias.jsonl')
            self.assertEqual((Path(folder) / 'licencias.jsonl').read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('baiona')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36003')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
