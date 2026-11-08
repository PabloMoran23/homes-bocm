"""Offline parser and contract tests. Run: python -m unittest municipio.test_caspe -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.caspe import (
    CaspeAyuntamientoAdapter, ROOT, SOURCE, parse_directory, parse_portal,
)
from municipio.manifest import load_manifest, load_yaml

PORTAL = '''<div class="entry-content"><div class="wpb_accordion_section">
<h3>PGOU</h3><a href="https://www.caspe.es/pgou/">PGOU</a></div>
<div class="wpb_accordion_section"><h3>Obra mayor</h3>
<a href="/instancia.pdf">Solicitud de licencia</a></div></div>'''


def index(url, links):
    from urllib.parse import urlsplit
    return '<h1>Index of ' + urlsplit(url).path.rstrip('/') + '</h1><pre>' + ''.join(
        '<a href="' + link + '">truncated..&gt;</a>' for link in links
    ) + '</pre>'


class CaspeTests(unittest.TestCase):
    def test_portal_requires_pgou_section_not_form(self):
        self.assertEqual(parse_portal(PORTAL), ROOT)
        with self.assertRaises(ValueError):
            parse_portal(PORTAL.replace('<h3>PGOU</h3>', '<h3>Licencias</h3>'))
        with self.assertRaises(ValueError):
            parse_portal('<html>Unavailable</html>')

    def test_directory_full_filename_and_sort_links(self):
        children, docs = parse_directory(index(ROOT, [
            '?C=N;O=D', '/', 'texto/', 'CAT%C3%81LOGO%20ARQUEOL%C3%93GICO.pdf',
            'https://example.org/external.pdf',
        ]), ROOT)
        self.assertEqual(children, [ROOT + 'texto/'])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['titulo'], 'CATÁLOGO ARQUEOLÓGICO')
        self.assertEqual(docs[0]['inventory_url'], ROOT)

    def test_pagination_and_changed_layout_fail(self):
        for html in [index(ROOT, ['?page=2']),
                     index(ROOT, []) + '<a href="/next" rel="next">2</a>',
                     '<h1>Error</h1><pre></pre>', index(ROOT, ['data.zip'])]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_directory(html, ROOT)

    def pages(self):
        return {
            SOURCE: PORTAL,
            ROOT: index(ROOT, ['texto/', 'planos/']),
            ROOT + 'texto/': index(ROOT + 'texto/', [
                '../', 'NORMAS%20URBANISTICAS.pdf', 'estudios/',
                'NORMAS%20URBANISTICAS.pdf',
            ]),
            ROOT + 'texto/estudios/': index(ROOT + 'texto/estudios/', ['Trafico.pdf']),
            ROOT + 'planos/': index(ROOT + 'planos/', ['Ordenacion.pdf']),
        }

    def test_recursive_grouping_and_refresh(self):
        adapter = CaspeAyuntamientoAdapter('caspe')
        pages = self.pages()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(report['documents'], 3)
            self.assertEqual(len(row['documentos']), 3)
            self.assertEqual(len(row['source_urls']), len(pages))
            for forbidden in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(forbidden, row)
            before = out.read_text()
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), before)

    def test_fetch_failure_does_not_replace_existing_output(self):
        adapter = CaspeAyuntamientoAdapter('caspe')
        pages = self.pages()
        del pages[ROOT + 'texto/estudios/']
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous output')
            with self.assertRaises(KeyError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous output')

    def test_empty_archive_rejected(self):
        adapter = CaspeAyuntamientoAdapter('caspe')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[PORTAL, index(ROOT, [])]):
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(Path(tmp) / 'rows.jsonl')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('caspe')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('50074', 'Zaragoza'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = CaspeAyuntamientoAdapter('caspe')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
