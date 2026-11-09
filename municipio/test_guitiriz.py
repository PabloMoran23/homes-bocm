import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.guitiriz import GuitirizAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest

HTML = '''<h1>Urbanismo e medio ambiente</h1>
<a href="https://www.dropbox.com/s/example/PXOM.zip?dl=0">Acceso ao Plan Xeral</a>
<div class="vc_column_container"><h3>Plantexamento de desenvolvemento</h3>
<div class="btn-caja"><a href="/docs/a.pdf">Estudo Detalle Rúa A</a>
<a href="/docs/b.pdf">Planos</a><a href="/docs/a.pdf">Duplicado</a></div>
<div class="btn-caja"><a href="/docs/c.pdf">Plan Especial Rúa B</a></div></div>
<a href="/docs/form.pdf">Solicitude de licenza urbanística</a>
<a href="/docs/fire.pdf">Plan Municipal Prevencion de Incendios</a>
<a href="/news/work">Licitación de obras</a>'''


class GuitirizTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 1])
        self.assertEqual(rows[1]['documentos'][1]['url'], 'https://concellodeguitiriz.com/docs/b.pdf')
        self.assertNotIn('b.pdf', json.dumps(rows[2]))
        self.assertNotIn('form.pdf', json.dumps(rows))
        self.assertNotIn('fire.pdf', json.dumps(rows))

    def test_no_invented_semantics(self):
        for row in parse_inventory(HTML):
            self.assertEqual(row['codigo_ine'], '27022')
            self.assertFalse(row['publication_ready'])
            self.assertFalse({'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                              'lat', 'lon', 'fase'} & row.keys())

    def test_stable_identity_and_unicode(self):
        rows = parse_inventory(HTML)
        changed = parse_inventory(HTML.replace('/docs/a.pdf', '/docs/new.pdf'))
        self.assertEqual(rows[1]['id'], changed[1]['id'])
        decomposed = parse_inventory(HTML.replace('Rúa A', 'Ru\u0301a A'))
        self.assertEqual(rows[1]['id'], decomposed[1]['id'])

    def test_reject_missing_and_unknown_inventory(self):
        for html in ['', HTML.replace('Plantexamento de desenvolvemento', 'Changed'),
                     HTML.replace('Estudo Detalle Rúa A', 'Solicitude licenza'),
                     HTML.replace('https://www.dropbox.com', 'https://example.org')]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_explicitly(self):
        for link in ['<a rel="next" href="?page=2">2</a>',
                     '<div class="pagination">2</div>', '<a href="?page=2">Seguinte</a>']:
            with self.assertRaisesRegex(ValueError, 'page|Pagination'):
                parse_inventory(HTML + link)

    def test_live_path_and_update_snapshot(self):
        response = Mock(text=HTML, url=SOURCE, headers={'Content-Type': 'text/html; charset=UTF-8'})
        adapter = GuitirizAyuntamientoAdapter('guitiriz')
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.guitiriz.requests.get', return_value=response) as fetch:
            output = Path(directory) / 'out.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(output.read_text().splitlines()), 3)
            fetch.assert_called_once()
            response.raise_for_status.assert_called_once()
            response.text = '<h1>Maintenance</h1>'
            previous = output.read_text()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(previous, output.read_text())

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.guitiriz.requests.get') as fetch:
            output = Path(directory) / 'lic.jsonl'
            result = GuitirizAyuntamientoAdapter('guitiriz').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')
            fetch.assert_not_called()

    def test_manifest(self):
        manifest = load_manifest('guitiriz')
        self.assertEqual(manifest.provincia, 'Lugo')
        self.assertTrue(manifest.proyectos.enabled)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.guitiriz:GuitirizAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
