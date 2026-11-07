"""Offline parser contract tests; no external services required."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from municipio.adapters.ordizia import BASE, INVENTORY, PLAN, OrdiziaAyuntamientoAdapter
from municipio.manifest import load_manifest

INVENTORY_HTML = '''<section id="sp-main-body">
<a href="/es/plan-general-de-ordenacion-urbana">Revisión del Plan General</a>
<a href="/media/study.pdf">Estudio de detalle "Urdaneta 36-38"</a>
<a href="/media/study.pdf">Estudio de detalle "Urdaneta 36-38"</a>
<a href="/tramites/licencia.pdf">Solicitud de licencia de obras</a>
<a href="/news/contract">Licitación obras</a></section>'''
PLAN_HTML = '''<section id="sp-main-body"><div class="dropfiles-content-tree" data-category="196">
<h2 class="tree-category-title">PLAN GENERAL DE ORDENACIÓN URBANA - Avance 2017</h2>
<a class="catlink" data-idcat="197" href="#">Memoria</a></div></section>'''


def payloads():
    return {
        ('frontcategories', 196): {'category': {'id': 196}, 'categories': [
            {'id': 197, 'parent_id': 196, 'title': 'Memoria', 'files': 1}]},
        ('frontfiles', 196): {'category': {'id': 196}, 'files': []},
        ('frontcategories', 197): {'category': {'id': 197}, 'categories': []},
        ('frontfiles', 197): {'category': {'id': 197}, 'files': [
            {'id': 42, 'catid': 197, 'title': 'Memoria del avance', 'ext': 'pdf',
             'link': BASE + '/files/197/42/memoria', 'created_time': '2017-11-08'}]},
    }


def getter(data):
    def fetch(url):
        q = parse_qs(urlparse(url).query)
        return copy.deepcopy(data[(q['view'][0], int(q['id'][0]))])
    return fetch


class OrdiziaTests(unittest.TestCase):
    def test_inventory_excludes_forms_and_groups_repeated_documents(self):
        rows = OrdiziaAyuntamientoAdapter.parse_inventory(INVENTORY_HTML)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['documentos'][0]['url'], BASE + '/media/study.pdf')
        self.assertEqual(rows[0]['codigo_ine'], '20076')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertNotIn('fase', rows[0])
        moved = INVENTORY_HTML.replace('/media/study.pdf', '/media/2026/02/09/study.pdf')
        self.assertEqual(rows[0]['id'], OrdiziaAyuntamientoAdapter.parse_inventory(moved)[0]['id'])

    def test_nested_documents_form_one_plan_and_upload_date_stays_on_document(self):
        row = OrdiziaAyuntamientoAdapter.parse_plan(PLAN_HTML, getter(payloads()))
        self.assertEqual(row['id'], 'ordizia-proy-pgou-196')
        self.assertEqual(row['fase'], 'avance')
        self.assertEqual(row['categorias_recorridas'], 2)
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['fecha_alta_documento'], '2017-11-08')
        self.assertEqual(row['documentos'][0]['carpeta'], ['Memoria'])
        for key in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'geometry', 'lat', 'lon']:
            self.assertIsNone(row[key])

    def test_incomplete_responses_fail_instead_of_truncating(self):
        for mutation in ['count', 'pagination', 'cycle', 'empty', 'foreign', 'missing_category']:
            with self.subTest(mutation=mutation):
                data = payloads()
                if mutation == 'count':
                    data[('frontcategories', 196)]['categories'][0]['files'] = 2
                elif mutation == 'pagination':
                    data[('frontfiles', 197)]['next'] = '/page2'
                elif mutation == 'cycle':
                    data[('frontcategories', 197)]['categories'] = [
                        {'id': 196, 'parent_id': 197, 'title': 'Cycle', 'files': 0}]
                elif mutation == 'empty':
                    data[('frontcategories', 196)]['categories'][0]['files'] = 0
                    data[('frontfiles', 197)]['files'] = []
                elif mutation == 'missing_category':
                    data[('frontcategories', 196)]['categories'] = []
                else:
                    data[('frontfiles', 197)]['files'][0]['link'] = 'https://example.com/file.pdf'
                with self.assertRaises(ValueError):
                    OrdiziaAyuntamientoAdapter.parse_plan(PLAN_HTML, getter(data))

    def test_changed_html_and_pagination_fail(self):
        for html in ['', INVENTORY_HTML + '<div></div>', INVENTORY_HTML.replace('</section>', '<a rel="next" href="?start=10">Next</a></section>')]:
            if html == INVENTORY_HTML + '<div></div>':
                html = html.replace('Revisión del Plan General', 'Removed')
            with self.assertRaises(ValueError):
                OrdiziaAyuntamientoAdapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            OrdiziaAyuntamientoAdapter.parse_plan(PLAN_HTML.replace('Avance 2017', 'Aprobación definitiva'), getter(payloads()))

    def test_disabled_licences_and_manifest(self):
        manifest = load_manifest('ordizia')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            adapter = OrdiziaAyuntamientoAdapter()
            with patch('requests.Session.get', side_effect=AssertionError('Licences must not fetch')):
                result = adapter.update_licencias(out, Path(d) / 'state.json')
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
