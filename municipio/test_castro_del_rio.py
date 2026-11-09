import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.castro_del_rio import CastroDelRioAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest

URL = 'https://castrodelrio.es/plan-parcial-para-el-desarrollo-del-sector-pp-4/'
INVENTORY = '''<article><h2 class="vcex-blog-entry-title"><a href="%s">Plan Parcial para el Desarrollo del Sector PP-4</a></h2>
<h2 class="vcex-blog-entry-title"><a href="%s">Plan Parcial para el Desarrollo del Sector PP-4</a></h2>
<h2 class="vcex-blog-entry-title"><a href="/guia-de-movilidad/">Guía de Movilidad</a></h2></article>''' % (URL, URL)
DETAIL = '''<article class="single-blog-article"><h1 class="entry-title">Plan Parcial para el Desarrollo del Sector PP-4</h1>
<time itemprop="datePublished" datetime="2022-04-28">28/04/2022</time>
<div class="single-blog-content"><p>Documento técnico: <a href="http://afosoftservices.com/wordpress/wp-content/uploads/2022/04/TECNICO.pdf">PDF</a></p>
<p>Resumen: <a href="/wp-content/uploads/2022/04/RESUMEN.pdf">PDF</a></p>
<p>Duplicado: <a href="/wp-content/uploads/2022/04/RESUMEN.pdf">PDF</a></p></div></article>'''


class CastroDelRioTests(unittest.TestCase):
    def test_manifest(self):
        m = load_manifest('castro-del-rio')
        self.assertEqual((m.nombre, m.provincia, m.portal.config['ine_code']), ('Castro del Río', 'Córdoba', '14019'))
        self.assertFalse(m.licencias.enabled)

    def test_inventory_deduplicates_and_excludes_guide(self):
        self.assertEqual(Adapter.parse_inventory(INVENTORY), [URL])

    def test_pagination_never_silently_truncated(self):
        for extra in ['<div class="pagination"><a href="/page/2/">2</a></div>',
                      '<a rel="next" href="/next/">More</a>', '<a href="?paged=2">2</a>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_inventory(INVENTORY + extra)

    def test_grouping_and_semantics(self):
        row = Adapter.parse_project(DETAIL, URL)
        self.assertEqual(row['fecha_publicacion'], '2022-04-28')
        for key in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][0]['url'].startswith('http://afosoftservices.com/'))
        self.assertEqual(row['documentos'][0]['source_url'], URL)
        self.assertEqual(row['id'], Adapter.parse_project(DETAIL.replace('2022-04-28', '2023-01-01'), URL)['id'])

    def test_no_publication_date_is_not_invented(self):
        self.assertIsNone(Adapter.parse_project(DETAIL.replace('datetime="2022-04-28"', ''), URL)['fecha_publicacion'])
        with self.assertRaises(ValueError):
            Adapter.parse_project(DETAIL.replace('2022-04-28', '2022-99-99'), URL)

    def test_no_navigation_form_or_documentless_records(self):
        for html in ['<a href="plan.pdf">Plan Parcial</a>', '<h1>Login</h1>',
                     DETAIL.replace('Plan Parcial para el Desarrollo del Sector PP-4', 'Solicitud de licencia'),
                     DETAIL.replace('.pdf', '.txt')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_project(html, URL)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<a href="/plan/">Plan Parcial</a>')

    def test_external_detail_is_rejected(self):
        with self.assertRaises(ValueError):
            Adapter.parse_project(DETAIL, 'https://example.org/plan/')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(INVENTORY.replace(URL, 'https://example.org/plan/'))

    def test_complete_refresh_and_failure_preserves_output(self):
        adapter = Adapter('castro-del-rio')
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, DETAIL]):
                result = adapter.update_proyectos(output, Path(d) / 'state.json')
            self.assertEqual(result['rows'], 1)
            old = output.read_text()
            self.assertEqual(json.loads(old)['codigo_ine'], '14019')
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), old)
            self.assertEqual(adapter.backfill_licencias(Path(d) / 'licencias.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
