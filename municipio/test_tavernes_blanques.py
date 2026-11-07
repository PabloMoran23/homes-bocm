"""Offline parser/contract tests; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.tavernes_blanques import (
    SOURCE, TavernesBlanquesAyuntamientoAdapter, decode_html, parse_directory,
)
from municipio.entity_policy import classify
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def listing(*hrefs):
    return ('<h1 id="indextitle">Index of /register</h1><table id="indexlist">' +
            ''.join(f'<tr><td class="indexcolname"><a href="{h}">{t}</a></td></tr>'
                    for h, t in hrefs) + '</table>')


class TavernesBlanquesTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TavernesBlanquesAyuntamientoAdapter('tavernes-blanques')
        self.category = SOURCE + '1%20P.%20GENERAL/'
        self.first = self.category + '46237-1101%20PGMOD%20n%ba11/'
        self.second = self.category + '46237-1103%20MPn%ba12/'
        self.pages = {
            SOURCE: listing(('1%20P.%20GENERAL/', '1 P. GENERAL/')),
            self.category: listing(
                ('46237-1101%20PGMOD%20n%ba11/', '46237-1101 PGMOD nº11/'),
                ('46237-1103%20MPn%ba12/', '46237-1103 MPnº12/'),
                ('EXPEDIENTES%20ANULADOS/', 'EXPEDIENTES ANULADOS/')),
            self.first: listing(('1%20APROBACION/', '1 APROBACION/'),
                                ('2%20MEMORIA/', '2 MEMORIA/'),
                                ('Thumbs.db', 'Thumbs.db')),
            self.first + '1%20APROBACION/': listing(('BOP.pdf', 'PUBLICACIÓN BOP.pdf')),
            self.first + '2%20MEMORIA/': listing(('memoria.pdf', 'MEMORIA+PLANOS.pdf')),
            self.second: listing(('proyecto.pdf', 'Documento técnico.pdf')),
        }

    def test_groups_all_documents_and_excludes_annulled(self):
        fetched = []
        def fetch(url):
            fetched.append(url)
            return self.pages[url]
        rows, report = self.adapter.extract(fetch)
        self.assertEqual([r['expediente'] for r in rows], ['46237-1101', '46237-1103'])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['documentos'][0]['url'], self.first + '1%20APROBACION/BOP.pdf')
        self.assertEqual(rows[1]['documentos'][0]['url'], self.second + 'proyecto.pdf')
        self.assertEqual(set(fetched), set(self.pages))
        self.assertEqual(len(report['excluded_urls']), 1)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46237')
            self.assertEqual(classify(row)['entity_type'], 'expediente')
            self.assertEqual(row['source'], 'registro_planeamiento_gva')
            self.assertFalse(row['publication_ready'])
            self.assertFalse(any(k.startswith('fecha') or k in {'lat', 'lon', 'coordinates', 'fase'} for k in row))

    def test_directory_rejects_pagination_and_changed_markup(self):
        for html in ['<h1>Access denied</h1>', listing(),
                     listing(('a.pdf', 'a')) + '<a href="?page=2" rel="next">2</a>',
                     listing(('?page=2', '2'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_directory(html, SOURCE)

    def test_scope_and_duplicate_links(self):
        html = listing(('../', 'Parent'), ('https://example.org/x.pdf', 'Other'),
                       ('one.pdf', 'One'), ('one.pdf', 'One'))
        entries = parse_directory(html, SOURCE)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['url'], SOURCE + 'one.pdf')

    def test_missing_documents_fails_before_output(self):
        self.pages[self.second] = listing(('Thumbs.db', 'Thumbs.db'))
        with self.assertRaisesRegex(ValueError, 'lacks documents'):
            self.adapter.extract(self.pages.__getitem__)

    def test_duplicate_instrument_fails(self):
        self.pages[self.category] = listing(
            ('46237-1101%20A/', '46237-1101 A/'), ('46237-1101%20B/', '46237-1101 B/'))
        with self.assertRaisesRegex(ValueError, 'Duplicate register identity'):
            self.adapter.extract(self.pages.__getitem__)

    def test_latin1_filenames_and_utf8(self):
        self.assertEqual(decode_html('APROBACIÓN nº12'.encode('latin-1')), 'APROBACIÓN nº12')
        self.assertEqual(decode_html('APROBACIÓN nº12'.encode('utf-8')), 'APROBACIÓN nº12')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tavernes-blanques')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, TavernesBlanquesAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            report = adapter.backfill_licencias(path)
            self.assertTrue(report['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_update_writes_full_snapshot(self):
        # Exercise real HTTP-facing entrypoint with a deterministic directory transport.
        self.adapter._fetch = lambda session, url: self.pages[url]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('{"id":"stale"}\n')
            report = self.adapter.update_proyectos(path, Path(tmp) / 'unused-state')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(report['count'], 2)
            self.assertEqual(len(rows), 2)
            self.assertNotIn('stale', [r['id'] for r in rows])


if __name__ == '__main__':
    unittest.main()
