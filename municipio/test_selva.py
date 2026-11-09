import tempfile
import unittest
from pathlib import Path

from municipio.adapters.selva import INVENTORIES, SelvaAyuntamientoAdapter, parse_page
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, body):
    return '<main><div class="layout-content"><h1>' + title + '</h1>' + body + '</div></main>'


def attachment(title, name='notice.pdf'):
    return ('<article class="node-file-or-document"><div><h3>' + title + '</h3>'
            '<span>03/08/2026</span><a download href="/sites/cilma_selva/files/' + name +
            '">Descarregar</a></div></article>')


class SelvaTests(unittest.TestCase):
    def test_group_tree_and_retain_provenance(self):
        pages = {}
        for root, title, _ in INVENTORIES:
            child = root + '/documents'
            pages[root] = page(title, '<div class="taxonomy-term-files"><a href="' + child +
                               '"><h3>Documents</h3></a></div>')
            pages[child] = page('Documents', attachment('Memòria', 'memory.pdf') + attachment('Plànols', 'maps.pdf'))
        rows = SelvaAyuntamientoAdapter('selva').collect_projects(pages.__getitem__)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(rows[0]['documentos'][0]['url_origen'], INVENTORIES[0][0] + '/documents')
        self.assertEqual(rows[0]['paginas_fuente'], sorted([INVENTORIES[0][0], INVENTORIES[0][0] + '/documents']))
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['geometry'])

    def test_bulletin_date_is_not_upload_or_agreement_date(self):
        _, _, docs = parse_page(page('Notice', attachment('00-Boib 103 de 06-06-2020 PDSU.pdf')), INVENTORIES[0][0])
        self.assertEqual(docs[0]['fecha_publicacion_boib'], '2020-06-06')
        _, _, docs = parse_page(page('Memory', attachment('Memòria')), INVENTORIES[0][0])
        self.assertIsNone(docs[0]['fecha_publicacion_boib'])

    def test_refuse_pagination(self):
        for pager in ['<nav class="pager">2</nav>', '<a href="?page=1">2</a>', '<a rel="next" href="/next">Next</a>']:
            with self.assertRaises(ValueError):
                parse_page(page('Plan', attachment('Memory') + pager), INVENTORIES[0][0])

    def test_refuse_navigation_forms_and_missing_documents(self):
        for body in ['<a href="/forms/licence.pdf">Sol·licitud</a>', '<p>Login</p>']:
            with self.assertRaises(ValueError):
                parse_page(page('Urbanisme', body), INVENTORIES[0][0])
        with self.assertRaises(ValueError):
            parse_page('<h1>Login</h1>', INVENTORIES[0][0])

    def test_refuse_external_attachment(self):
        with self.assertRaises(ValueError):
            parse_page(page('Plan', attachment('Memory').replace('/sites/cilma_selva/files/notice.pdf', 'https://example.org/a.pdf')), INVENTORIES[0][0])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('selva')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(target)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
