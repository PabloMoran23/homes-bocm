"""Offline parser/crawler contract tests; run with python -m unittest municipio.test_porreres."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.porreres import (
    BASE, SOURCE, PorreresAyuntamientoAdapter, instrument_key, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def folder(links, pager=''):
    cards = ''.join(f'<a href="{url}"><h3>{title}</h3></a>' for url, title in links)
    return f'<main><div class="layout-content"><h1>Expedients</h1><div class="taxonomy-term-files">{cards}</div>{pager}</div></main>'


def document(title='Memòria', filename='memoria.pdf', date='28/04/2022'):
    return f'''<main><div class="layout-content"><h1>Modificació NNSS</h1>
    <article class="node-file-or-document"><div class="prose">Expedient 343/2020.</div>
    <section class="multimedia--documents"><div><h3>{title}</h3><span>PDF · {date}</span>
    <a href="/sites/cilma_porreres/files/{filename}" download>Descarregar</a></div></section>
    </article></div></main>'''


class PorreresTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PorreresAyuntamientoAdapter('porreres')

    def test_metadata_dates_are_not_approval_dates(self):
        parsed = parse_page(document('Certificat acord Ple 28 març 2022'), SOURCE + '/test')
        doc = parsed['documentos'][0]
        self.assertEqual(doc['fecha_archivo'], '2022-04-28')
        self.assertNotIn('fecha_acuerdo', doc)
        self.assertEqual(parsed['descripcion'], 'Expedient 343/2020.')
        self.assertEqual(doc['pagina_origen'], SOURCE + '/test')

    def test_collect_all_pages_group_versions_deduplicate_docs(self):
        root1 = BASE + '/ca/arxius-i-documents/adaptacio-nnss-al-ptm'
        root2 = SOURCE + '/text-refos-modificacio-nnss-i-adaptacio-al-ptm-2021'
        child = root1 + '/memoria'
        next_page = SOURCE + '?page=1'
        html = {
            SOURCE: folder([(root1, 'Adaptació NNSS al PTM')],
                           '<nav class="pager"><a href="?page=1" rel="next">Següent</a></nav>'),
            next_page: folder([(root2, 'Text refós 2021')]),
            root1: folder([(child, 'Memòria')]),
            child: document(), root2: document(),
        }
        calls = []
        def fetch(url):
            calls.append(url)
            return parse_page(html[url], url)
        rows, sources = self.adapter.collect(fetch)
        self.assertEqual(set(calls), set(html))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(len(rows[0]['documentos'][0]['apariciones']), 2)
        self.assertEqual(set(sources), set(html))
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])
        self.assertFalse(rows[0]['publication_ready'])
        self.assertEqual(rows[0]['numero_expediente'], '343/2020')

    def test_navigation_forms_and_road_catalogue_excluded(self):
        html = folder([]).replace('<h1>', '<aside><a href="/forms">Llicència</a></aside><h1>', 1)
        self.assertEqual(parse_page(html, SOURCE)['children'], [])
        self.assertIsNone(instrument_key(BASE + '/ca/arxius-i-documents/cataleg-de-camins'))
        with self.assertRaises(ValueError):
            instrument_key(SOURCE + '/sollicitud-llicencia')

    def test_new_inventory_branch_requires_review(self):
        with self.assertRaises(ValueError):
            self.adapter.collect(lambda url: parse_page(folder([(SOURCE + '/new-plan', 'Nou pla')]), url))

    def test_reject_empty_broken_and_external_sources(self):
        for html in ('<html>Access denied</html>',
                     '<main><div class="layout-content"><h1>Document</h1><article class="node-file-or-document"></article></div></main>',
                     document().replace('/sites/cilma_porreres/files/memoria.pdf', 'https://example.org/file.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, SOURCE)
        with self.assertRaises(ValueError):
            self.adapter.collect(lambda url: parse_page(folder([]), url))

    def test_pagination_cannot_escape_branch(self):
        with self.assertRaises(ValueError):
            parse_page(folder([], '<nav class="pager"><a href="/ca/elsewhere?page=1">Next</a></nav>'), SOURCE)

    def test_cycles_terminate_and_licenses_are_disabled(self):
        root = SOURCE + '/modificacio-puntual-num-4-nnss'
        pages = {SOURCE: folder([(root, 'Modificació puntual núm. 4 NNSS')]),
                 root: document().replace('</article>', '</article><div class="taxonomy-term-files"><a href="' + root + '"><h3>Same instrument</h3></a></div>')}
        rows, _ = self.adapter.collect(lambda url: parse_page(pages[url], url))
        self.assertEqual(rows[0]['id'], 'porreres-proy-nnss-mp-4')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(self.adapter.update_licencias(out, Path(tmp) / 'state')['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        raw = load_yaml(Path('data/municipios/porreres/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '07043')
        self.assertEqual(raw['provincia'], 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(load_manifest('porreres').licencias.enabled)


if __name__ == '__main__':
    unittest.main()
