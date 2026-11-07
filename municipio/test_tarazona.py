import tempfile
import unittest
from pathlib import Path

from municipio.adapters.tarazona import SOURCE, TarazonaAyuntamientoAdapter, collect_projects, parse_page
from municipio.manifest import load_manifest, load_yaml


def page(title, content='', nav=''):
    return ('<div id="block-system-main"><h1>' + title + '</h1>'
            '<div class="field-name-body">' + content + '</div>' + nav + '</div>')


def link(url, title='documento'):
    return '<a href="' + url + '">' + title + '</a>'


class TarazonaTests(unittest.TestCase):
    def test_group_documents_provenance_and_pagination(self):
        doc = '/sites/default/files/texto_refundido.pdf'
        child = SOURCE + '/documentacion-grafica'
        second = child + '?page=1'
        pages = {
            SOURCE: page('Plan General Ordenación Urbana', link(doc), link(child)),
            child: page('Planos', link(doc, 'Otra etiqueta') + link('/sites/default/files/plano.jpg'),
                        '<ul class="pager"><li>' + link(second) + '</li></ul>' + link(SOURCE)),
            second: page('Planos', link('/sites/default/files/plano2.pdf'), link(child)),
        }
        calls = []
        def fetch(url):
            calls.append(url)
            return pages[url]
        rows = collect_projects(fetch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(len(calls), 3)
        refundido = next(d for d in rows[0]['documentos'] if d['url'].endswith('texto_refundido.pdf'))
        self.assertEqual(refundido['source_pages'], [SOURCE, child])
        self.assertEqual([r['titulo'] for r in refundido['apariciones']], ['documento', 'Otra etiqueta'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['geometry'])
        self.assertNotIn('fase', rows[0])

    def test_excludes_navigation_forms_and_foreign_files(self):
        html = page('Plan General', link('/formulario-licencia') + link('https://example.org/a.pdf'),
                    link('/sites/default/files/unrelated.pdf'))
        self.assertEqual(parse_page(html, SOURCE)[1], [])
        with self.assertRaises(ValueError):
            collect_projects(lambda _: html)

    def test_fail_closed_changed_markup_and_outside_pager(self):
        for html in ['<h1>Login</h1>', page('Plan General', '', '<div class="pager">' + link('https://example.org/?page=2') + '</div>')]:
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    def test_failed_later_page_does_not_return_partial_records(self):
        def fetch(url):
            if url != SOURCE:
                raise OSError('source unavailable')
            return page('Plan General', link('/sites/default/files/texto_refundido.pdf'), link(SOURCE + '/next'))
        with self.assertRaises(OSError):
            collect_projects(fetch)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tarazona')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('50251', 'Zaragoza'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'licencias.jsonl'
            self.assertTrue(TarazonaAyuntamientoAdapter().backfill_licencias(target)['disabled'])
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
