import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from municipio.adapters.castro_de_rei import (
    CastroDeReiAyuntamientoAdapter, MANAGER, PLAN, SOURCE, canonical,
    parse_directory, parse_plan,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def listing(folders=(), files=(), extra=''):
    body = '<div class="bold group"><a href="?path=*">...</a></div>'
    body += ''.join(f'<div class="directory group"><a href="?path={p}/*">folder</a></div>' for p in folders)
    body += ''.join(f'<div class="group"><div class="name"><a href="http://castroderei.gal/archivos/{PLAN}/{f}">{f}</a></div></div>' for f in files)
    return f'<section>{body}{extra}<footer>{len(folders)} carpeta/s y {len(files)} archivo/s</footer></section>'


class CastroDeReiTests(unittest.TestCase):
    def setUp(self):
        self.adapter = CastroDeReiAyuntamientoAdapter('castro-de-rei')
        self.plan = '<article><div class="entry-content"><p>PLAN GENERAL DE ORDENACIÓN MUNICIPAL DE CASTRO DE REI (Documento aprobado definitivo)</p><iframe src="/archivos/file_manager.php"></iframe></div></article>'
        self.root = canonical(MANAGER + '?path=' + PLAN + '/*')
        self.child = canonical(MANAGER + '?path=' + PLAN + '/TOMO I/*')
        self.pages = {SOURCE: self.plan, MANAGER: listing([PLAN]),
                      self.root: listing([PLAN + '/TOMO I'], ['normativa.pdf']),
                      self.child: listing(files=['TOMO I/plano 1.pdf', 'TOMO I/plano 1.pdf'])}

    def test_recursive_grouping_and_provenance(self):
        fetched = []
        def fetch(url):
            fetched.append(url)
            return self.pages[url]
        rows = self.adapter.extract(fetch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(set(fetched), set(self.pages))
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['geometry'])
        self.assertIn('http://castroderei.gal/', rows[0]['documentos'][0]['url_fuente'])
        self.assertTrue(all(d['inventario_url'] in fetched for d in rows[0]['documentos']))

    def test_changed_source_and_incomplete_listing_rejected(self):
        for html in ('<a href="/es/pxom/">PXOM</a>', self.plan.replace('aprobado definitivo', 'en tramitación')):
            with self.assertRaises(ValueError):
                parse_plan(html)
        for html in (listing(files=['a.pdf']).replace('1 archivo/s', '2 archivo/s'),
                     listing(extra='<a href="?page=2">Siguiente</a>'), '<section>error</section>',
                     listing(files=['a.pdf']).replace('http://castroderei.gal', 'https://example.com')):
            with self.assertRaises(ValueError):
                parse_directory(html, self.root)

    def test_cycle_and_empty_archive_rejected(self):
        self.pages[self.child] = listing([PLAN + '/TOMO I'])
        with self.assertRaises(ValueError):
            self.adapter.extract(self.pages.__getitem__)
        self.pages[self.root] = listing()
        with self.assertRaises(ValueError):
            self.adapter.extract(self.pages.__getitem__)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('castro-de-rei')
        adapter = load_portal_adapter(manifest)
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(adapter, CastroDeReiAyuntamientoAdapter)
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
