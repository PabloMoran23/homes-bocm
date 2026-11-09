"""Offline parser/crawler regression tests; live evidence is kept separately."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.gerena import (
    SOURCE, GerenaAyuntamientoAdapter, extract_inventory, parse_sections,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

BASE = '/export/sites/gerena/es/transparencia/.galleries/IND-53-/'


def gallery(title, files, page=None, current='1'):
    links = ''.join(f'<a href="{BASE}{f}">{f}</a>' for f in files)
    pager = ''
    if page:
        pager = (f'<a class="currentpagelink" numpag="{current}" href="?pagegalleryfiles-3-1={current}">{current}</a>'
                 '<a class="pagelink" href="?pagegalleryfiles-3-1=2#galleryfiles-3-1">2</a>')
    return (f'<section class="gallery"><h4 class="gallery-title">{title}</h4>'
            f'<div class="download-group" id="{"galleryfiles-3-1" if page else "galleryfiles-4-1"}">{links}{pager}</div></section>')


class GerenaTests(unittest.TestCase):
    def test_pagination_groups_documents_without_other_gallery_contamination(self):
        first = gallery('Modificación 1. Fontanilla', ['font/memoria.pdf'], page=True)
        first += gallery('ED Lumbreras', ['lumbreras/plano.pdf'])
        second = gallery('Modificación 1. Fontanilla', ['font/plano.pdf'], page=True, current='2')
        second += gallery('ED Lumbreras', ['lumbreras/plano.pdf'])
        seen = []

        def fetch(url):
            seen.append(url)
            return second if 'pagegalleryfiles-3-1=2' in url else first

        rows, urls = extract_inventory(fetch)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen, urls)
        self.assertEqual(rows[0]['codigo_ine'], '41045')
        self.assertFalse(rows[0]['publication_ready'])
        for row in rows:
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)

    def test_ignored_pagination_fails(self):
        first = gallery('ED Lumbreras', ['lumbreras/plano.pdf'], page=True)
        with self.assertRaisesRegex(ValueError, 'requested page'):
            extract_inventory(lambda _: first)

    def test_repeated_page_fails_even_with_current_page_marker(self):
        def fetch(url):
            return gallery('ED Lumbreras', ['lumbreras/plano.pdf'], page=True,
                           current='2' if '=2' in url else '1')
        with self.assertRaisesRegex(ValueError, 'Repeated gallery page'):
            extract_inventory(fetch)

    def test_missing_galleries_and_empty_gallery_fail(self):
        for html in ('<h1>Access denied</h1>', gallery('ED Lumbreras', [])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_sections(html)

    def test_external_document_rejected(self):
        html = gallery('ED Lumbreras', ['lumbreras/plano.pdf'])
        html = html.replace('href="/export', 'href="https://example.org/export')
        with self.assertRaisesRegex(ValueError, 'non-official'):
            parse_sections(html)

    def test_school_study_separate_and_non_pdf_links_retained(self):
        html = gallery('ED Equipamiento SUO1', [
            'ED-EQUIPAMIENTO-SUO1/16-ED.pdf',
            'ED-EQUIPAMIENTO-SUO1/ESTUDIO-DE-DETALLE.-2020.-COLEGIO/plano.tif',
            'ED-EQUIPAMIENTO-SUO1/ESTUDIO-DE-DETALLE.-2020.-COLEGIO/memoria.pdf'])
        rows, _ = extract_inventory(lambda _: html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2])
        self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_portal_timestamp_does_not_become_approval_date(self):
        html = ('<section class="gallery"><h4 class="gallery-title">Modificación PGOU</h4>'
                '<div class="media"><a href="' + BASE + '2026/ed.pdf">Estudio</a>'
                '<time datetime="2026-02-18T11:20:00.000+0100">18 febrero</time>'
                '<div class="description">Aprobación definitiva del Estudio de Detalle M-3-13-1</div>'
                '</div></section>')
        rows, _ = extract_inventory(lambda _: html)
        self.assertIn('M-3-13-1', rows[0]['titulo'])
        self.assertEqual(rows[0]['documentos'][0]['fecha_publicacion_portal'], '2026-02-18T11:20:00.000+0100')
        self.assertNotIn('fecha_aprob', rows[0])
        self.assertNotIn('fecha_publicacion', rows[0])

    def test_manifest_load_and_snapshot_and_disabled_licences(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/gerena/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual(raw['codigo_ine'], '41045')
        self.assertEqual(raw['provincia'], 'Sevilla')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        manifest = load_manifest(path)
        self.assertIsInstance(load_portal_adapter(manifest), GerenaAyuntamientoAdapter)
        adapter = GerenaAyuntamientoAdapter('gerena')
        with TemporaryDirectory() as folder:
            out = Path(folder) / 'rows.jsonl'
            out.write_text('old snapshot')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')
            with patch('municipio.adapters.gerena.requests.Session') as session:
                response = session.return_value.__enter__.return_value.get.return_value
                response.url = SOURCE
                response.text = gallery('ED Lumbreras', ['lumbreras/plano.pdf'])
                result = adapter.update_proyectos(out, Path(folder) / 'unused-state')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(out.read_text())['municipio'], 'Gerena')


if __name__ == '__main__':
    unittest.main()
