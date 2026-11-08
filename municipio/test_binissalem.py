"""Parser and adapter contract tests; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.binissalem import BinissalemAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def inventory(entries, extra=''):
    return ('<main><section><h1>Instruments de planejament en vigor</h1>'
            '<div class="content"><ul class="archive">' + entries
            + '</ul></div>' + extra + '</section></main>')


def link(title, path):
    return f'<li><a href="/wp-content/uploads/2018/06/{path}">{title}</a></li>'


FIXTURE = inventory(
    link('Normes subsidiàries', 'nnss.pdf')
    + link('Modificació puntual núm. 1', 'Modificació-1.pdf')
    + link('Modificació puntual núm. 2', 'mod2.pdf'))


class BinissalemTests(unittest.TestCase):
    def test_real_instruments_keep_unknown_dates_and_source_category(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['id'] for r in rows}), 3)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '07008')
            self.assertEqual(row['inventory_url'], SOURCE)
            self.assertEqual(row['clasificacion_fuente'], 'Instruments de planejament en vigor')
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[key])
        # A filename/upload year must not become an agreement/publication date.
        self.assertIn('/2018/06/', rows[0]['documentos'][0]['url'])

    def test_group_documents_and_deduplicate_without_losing_links(self):
        entries = (link('Modificació puntual núm. 1 - Memòria', 'memoria.pdf')
                   + link('Modificació puntual núm. 1 - Plànols', 'planols.pdf')
                   + link('Modificació puntual núm. 1 - Memòria', 'memoria.pdf'))
        row, = parse_inventory(inventory(entries))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['id'], parse_inventory(FIXTURE)[1]['id'])

    def test_fail_on_pagination_instead_of_truncating(self):
        for pagination in ['<a rel="next" href="/other">Més</a>',
                           '<a href="?paged=2">2</a>', '<div class="pagination">2</div>']:
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(inventory(link('Normes subsidiàries', 'nnss.pdf'), pagination))

    def test_reject_forms_navigation_login_and_unexpected_entries(self):
        invalid = ['<h1>Login</h1>', inventory(''),
                   inventory(link('Sol·licitud de llicència urbanística', 'form.pdf')),
                   inventory('<a href="https://example.org/plan.pdf">Normes subsidiàries</a>')]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_unicode_document_paths_and_scope(self):
        row = parse_inventory(FIXTURE)[1]
        self.assertIn('Modificacio%CC%81', row['documentos'][0]['url'])
        # Sidebar documents and notices are not instruments in this inventory.
        rows = parse_inventory(FIXTURE + '<aside><a href="news.pdf">Projecte notícia</a></aside>')
        self.assertEqual(len(rows), 3)

    def test_fetch_every_document_and_preserve_output_on_bad_attachment(self):
        adapter = BinissalemAyuntamientoAdapter('binissalem')
        def fetch(url, limit):
            return FIXTURE.encode() if url == SOURCE else b'%PDF-1.4 fixture'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=fetch) as request:
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            self.assertEqual(request.call_count, 4)
            original = output.read_text()
            self.assertTrue(all(json.loads(line)['documentos'][0]['sha256'] for line in original.splitlines()))
            with patch.object(adapter, '_fetch', side_effect=[FIXTURE.encode(), b'<html>login</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('binissalem')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07008')
        self.assertEqual(raw['provincia'], 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(output)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
