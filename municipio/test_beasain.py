"""Offline parser/crawl tests with synthetic DOCman markup, never evidence records."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.beasain import BeasainAyuntamientoAdapter, SOURCE, parse_page
from municipio.manifest import load_manifest, load_yaml


def page(docs='', folders='', pager=''):
    return ('<div class="com_docman"><div class="docman_category">Plan General</div>'
            '<table class="koowa_table--categories">' + folders + '</table>'
            '<table>' + docs + '</table><div class="k-pagination">' + pager + '</div></div>')


def document(identity='2019', title='Documento de prueba'):
    return (f'<tr class="docman_item"><td><a class="docman_track_download" data-id="{identity}" '
            f'data-title="{title}" href="{SOURCE}/{identity}-documento/file">PDF</a></td>'
            '<td><time itemprop="datePublished" datetime="2019-04-24 09:39:43">24 Abr 2019</time></td></tr>')


class BeasainTests(unittest.TestCase):
    def test_document_metadata_and_categories(self):
        docs, links = parse_page(page(document(), f'<a href="{SOURCE}/fase">Carpeta</a>'), SOURCE)
        self.assertEqual(docs[0]['titulo'], 'Documento de prueba')
        self.assertEqual(docs[0]['fecha_publicacion'], '2019-04-24')
        self.assertNotIn('fecha_aprob', docs[0])
        self.assertEqual(links, [SOURCE + '/fase'])

    def test_pagination_and_unrecognized_controls(self):
        _, links = parse_page(page(pager='<a href="?offset=20">Siguiente</a><a href="?offset=40">3</a>'), SOURCE)
        self.assertEqual(links, [SOURCE + '?offset=20', SOURCE + '?offset=40'])
        with self.assertRaises(ValueError):
            parse_page(page(pager='<button>Siguiente</button>'), SOURCE)

    def test_changed_markup_and_foreign_links_fail(self):
        for html in ['<h1>Home</h1>', page(folders='<a href="https://example.org/plan">Carpeta</a>'),
                     page('<tr class="docman_item"><td>Changed</td></tr>')]:
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    def test_complete_crawl_groups_versions_and_deduplicates(self):
        pages = {
            SOURCE: page(document(), f'<a href="{SOURCE}/fase">Fase</a>'),
            SOURCE + '/fase': page(document(), pager='<a href="?offset=20">2</a>'),
            SOURCE + '/fase?offset=20': page(document('2020'), f'<a href="{SOURCE}">Parent</a>'),
        }
        calls = []

        def get(url, **kwargs):
            calls.append(url)
            class Response:
                def raise_for_status(self):
                    pass
            response = Response()
            response.url, response.text = url, pages[url]
            response.content = response.text.encode()
            return response

        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', side_effect=get):
            out = Path(tmp) / 'proyectos.jsonl'
            result = BeasainAyuntamientoAdapter('beasain').backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['inventory_pages'], 3)
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(len(rows[0]['documentos'][0]['inventory_urls']), 2)
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[0]['fecha_publicacion'])

    def test_failure_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', side_effect=RuntimeError('offline')):
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(RuntimeError):
                BeasainAyuntamientoAdapter('beasain').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('beasain')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Beasain', 'Gipuzkoa', '20019'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = BeasainAyuntamientoAdapter('beasain').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
