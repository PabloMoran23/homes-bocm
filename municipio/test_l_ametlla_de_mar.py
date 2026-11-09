"""Offline parser/collection tests; fixture labels are synthetic, not evidence."""
import html
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.l_ametlla_de_mar import (
    BRANCH, LANDING, ROOT, LAmetllaDeMarAyuntamientoAdapter,
    collect_projects, directory_url, parse_listing,
)
from municipio.manifest import load_manifest, load_yaml


def listing(folders=(), files=()):
    rows = []
    for folder in folders:
        href = directory_url(folder).removeprefix(ROOT)
        rows.append(f'<li data-name="{html.escape(folder)}" data-href="{html.escape(href)}"></li>')
    for path in files:
        rows.append(f'<li data-name="{html.escape(path.rsplit("/", 1)[-1])}" '
                    f'data-href="{html.escape(path)}">'
                    '<span class="file-modified">2026-11-03 10:09:45</span></li>')
    return '<ul id="directory-listing">' + ''.join(rows) + '</ul>'


class PlanningTests(unittest.TestCase):
    def fixture(self):
        instrument = BRANCH + '/Sector Test'
        nested = instrument + '/Plànols'
        return {
            LANDING: '<iframe src="' + ROOT + '"></iframe>',
            ROOT: listing([BRANCH, '01. POUM']),
            directory_url(BRANCH): listing([instrument]),
            directory_url(instrument): listing([nested], [instrument + '/normes.pdf', instrument + '/Thumbs.db']),
            directory_url(nested): listing(files=[nested + '/mapa.pdf', nested + '/Text BOP.doc']),
        }

    def test_complete_recursive_grouping_and_date_semantics(self):
        pages = self.fixture()
        requested = []
        def fetch(url):
            requested.append(url)
            return pages[url]
        rows, urls = collect_projects(fetch)
        self.assertEqual(set(requested), set(pages))
        self.assertEqual(urls, requested)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '43013')
        self.assertEqual(len(row['documentos']), 3)
        self.assertTrue(any('%C3%A0' in d['url'] for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertEqual(row['documentos'][0]['fecha_modificacion_archivo'], '2026-11-03 10:09:45')
        self.assertFalse(row['publication_ready'])

    def test_stable_identity_and_document_deduplication(self):
        pages = self.fixture()
        rows, _ = collect_projects(pages.__getitem__)
        first = rows[0]
        u = directory_url(BRANCH + '/Sector Test')
        pages[u] = pages[u].replace('</ul>', pages[u].split('<ul id="directory-listing">')[1])
        second = collect_projects(pages.__getitem__)[0][0]
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(second['documentos']), 3)

    def test_pagination_rejected(self):
        for extra in ('<a href="?page=2">2</a>', '<a rel="next" href="?dir=x">Next</a>',
                      '<a href="?dir=x">Següent</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_listing(listing() + extra, BRANCH)

    def test_out_of_scope_and_traversal_rejected(self):
        for href in ('https://example.org/file.pdf', '?dir=../secrets', '03. Planejament derivat/../file.pdf'):
            fixture = '<ul id="directory-listing"><li data-name="bad" data-href="' + href + '"></li></ul>'
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_listing(fixture, BRANCH)

    def test_missing_source_structure_rejected(self):
        with self.assertRaises(ValueError):
            parse_listing('<html>Login / navigation only</html>', BRANCH)
        pages = self.fixture()
        pages[LANDING] = '<h1>Urbanisme</h1>'
        with self.assertRaises(ValueError):
            collect_projects(pages.__getitem__)

    def test_empty_or_loose_inventory_rejected(self):
        for replacement in (listing(), listing(files=[BRANCH + '/unclassified.pdf'])):
            pages = self.fixture()
            pages[directory_url(BRANCH)] = replacement
            with self.assertRaises(ValueError):
                collect_projects(pages.__getitem__)
        pages = self.fixture()
        pages[directory_url(BRANCH + '/Sector Test/Plànols')] = listing()
        pages[directory_url(BRANCH + '/Sector Test')] = listing()
        with self.assertRaises(ValueError):
            collect_projects(pages.__getitem__)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('l-ametlla-de-mar')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '43013')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = LAmetllaDeMarAyuntamientoAdapter(manifest.slug).backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
