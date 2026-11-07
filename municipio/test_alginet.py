import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.alginet import AlginetAyuntamientoAdapter, inventory_url, parse_page
from municipio.manifest import load_manifest, load_yaml


def block(title, links):
    return '<div class="widget_sow-editor"><div class="siteorigin-widget-tinymce"><h5>' + title + '</h5>' + links + '</div></div>'


def page(slug, html):
    return {'id': 926 if slug == 'pgou' else 3449, 'slug': slug, 'status': 'publish',
            'content': {'rendered': html}}


class AlginetTests(unittest.TestCase):
    def test_instruments_and_components(self):
        html = block("Pla General d'Urbanisme", '<a href="/pgou.pdf">PGOU</a>')
        html += block('Modificació del usos del Teatre Moderno', '<a href="/mod.pdf">Modificació (Pub. 02/2014)</a>')
        html += block('Modificació de normes', '<a href="/normes.pdf">Document (Pub. 24/07/2012)</a>')
        html += '<a href="/map.pdf">Plànol</a><a href="/map.pdf">Duplicate</a>'
        html += '<a href="https://unrelated.example/x.pdf">Other</a><a href="/llicencies/">Forms</a>'
        rows = parse_page(page('pgou', html), inventory_url('pgou'))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(rows[1]['documentos'][0]['fecha_publicacion_texto'], '02/2014')
        self.assertEqual(rows[2]['documentos'][0]['fecha_publicacion'], '2012-07-24')
        self.assertEqual(rows, parse_page(page('pgou', html), inventory_url('pgou')))
        for row in rows:
            for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)

    def test_pge_grouped(self):
        p = page('pla-general', '<h3>Versió preliminar del Pla General Estructural</h3>'
                 '<a href="/memoria.pdf">Memòria</a><a href="/plans.zip">Plànols</a>')
        rows = parse_page(p, inventory_url('pla-general'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertFalse(rows[0]['publication_ready'])

    def test_fail_closed(self):
        for html in ('', '<a href="/form.pdf">Llicència</a>',
                     '<h3>Versió preliminar</h3>', '<div class="pagination">2</div>'):
            with self.assertRaises(ValueError):
                parse_page(page('pgou', html), inventory_url('pgou'))
        with self.assertRaises(ValueError):
            parse_page(page('llicencies', '<a href="/obra.pdf">Obra major</a>'), 'x')

    def test_api_pagination_and_atomic_failure(self):
        adapter = AlginetAyuntamientoAdapter('alginet')
        response = Mock(url=inventory_url('pgou'), headers={'X-WP-TotalPages': '2'})
        response.json.return_value = [page('pgou', block("Pla General d'Urbanisme", '<a href="/pgou.pdf">PGOU</a>'))]
        failure = Mock()
        failure.raise_for_status.side_effect = RuntimeError('page 2 failed')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out.jsonl'
            output.write_text('previous output')
            with patch('municipio.adapters.alginet.requests.Session') as factory:
                session = factory.return_value.__enter__.return_value
                session.get.side_effect = [response, failure]
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(session.get.call_args_list[1].args[0], inventory_url('pgou', 2))
                self.assertEqual(output.read_text(), 'previous output')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alginet')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46031')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = AlginetAyuntamientoAdapter('alginet').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
