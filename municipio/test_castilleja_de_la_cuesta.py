"""Offline parser/contract tests using representative municipal gallery markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.castilleja_de_la_cuesta import (
    SOURCE, DOC_PREFIX, CastillejaDeLaCuestaAyuntamientoAdapter,
    collect_inventory, page_url, parse_inventory,
)
from municipio.entity_policy import classify
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def gallery(title, docs, pages=0, active=1):
    links = ''.join(f'<a href="{DOC_PREFIX}{name}.pdf">{name}</a>' for name in docs)
    pager = ''
    if pages:
        pager = '<ul class="pagination">' + ''.join(
            f'<li class="{"active" if n == active else ""}"><a href="?pagegalleryfiles-1-1={n}">{n}</a></li>'
            for n in range(1, pages + 1)) + (
                f'<li><a class="lastpagelink" href="?pagegalleryfiles-1-1={pages}">Last</a></li></ul>')
    return f'<section class="gallery"><h4 class="gallery-title">{title}</h4>{links}{pager}</section>'


def document(*galleries):
    return ('<article class="sg-indicador-trans"><h2 class="title">'
            'Modificaciones aprobadas del PGOU y los Planes parciales aprobados</h2>'
            '<div class="contentblock"><h3>PLAN PARCIAL EL VALLE</h3>'
            + ''.join(galleries) + '</div></article>')


class InventoryTests(unittest.TestCase):
    def test_pagination_groups_documents_and_retains_provenance(self):
        pages = {SOURCE: document(gallery('PLAN PARCIAL', ['memoria'], 2)),
                 SOURCE + '?pagegalleryfiles-1-1=1': document(gallery('PLAN PARCIAL', ['memoria'], 2)),
                 SOURCE + '?pagegalleryfiles-1-1=2': document(gallery('PLAN PARCIAL', ['plano'], 2, 2))}
        rows, visited = collect_inventory(pages.__getitem__)
        self.assertEqual(set(visited), set(pages))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['source_urls'], [SOURCE + '?pagegalleryfiles-1-1=2'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['lat'])
        self.assertNotIn('fase', rows[0])
        self.assertFalse(rows[0]['publication_ready'])
        self.assertEqual(classify(rows[0])['entity_type'], 'documento')
        self.assertFalse(classify(rows[0])['activity_eligible'])

    def test_no_document_leakage_and_no_empty_projects(self):
        html = document(gallery('PLAN PARCIAL', ['memoria', 'plano']),
                        gallery('PROYECTO REPARCELACION', ['reparcelacion']),
                        gallery('PROYECTO URBANIZACION', []))
        rows, _ = collect_inventory(lambda _: html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['codigo_ine'], '41029')

    def test_duplicate_instrument_gallery_collapsed(self):
        rows, _ = collect_inventory(lambda _: document(
            gallery('PLAN PARCIAL ANTERIOR 3-A', ['memoria', 'plano']),
            gallery('PLAN PARCIAL ANTERIOR', ['plano', 'memoria'])))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['inventory_headings']), 2)

    def test_ignored_or_repeated_pagination_fails(self):
        first = document(gallery('PLAN PARCIAL', ['memoria'], 2))
        with self.assertRaisesRegex(ValueError, 'honour'):
            collect_inventory(lambda _: first)
        with self.assertRaisesRegex(ValueError, 'repeats'):
            collect_inventory(lambda url: document(gallery(
                'PLAN PARCIAL', ['memoria'], 2, 2 if url.endswith('=2') else 1)))

    def test_disabled_last_control_uses_current_final_page(self):
        html = document(gallery('PLAN PARCIAL', ['plano'], 2, 2)).replace(
            'class="lastpagelink" href="?pagegalleryfiles-1-1=2"',
            'class="lastpagelink" href="#galleryfiles-1-1"')
        _, pages = parse_inventory(html, SOURCE + '?pagegalleryfiles-1-1=2')
        self.assertEqual(len(pages), 2)

    def test_phantom_next_link_beyond_last_is_not_followed(self):
        first = document(gallery('PLAN PARCIAL', ['memoria'], 2))
        second = document(gallery('PLAN PARCIAL', ['plano'], 2, 2)).replace(
            '</ul>', '<li><a href="?pagegalleryfiles-1-1=3">Next</a></li></ul>')
        pages = {SOURCE: first, SOURCE + '?pagegalleryfiles-1-1=1': first,
                 SOURCE + '?pagegalleryfiles-1-1=2': second}
        rows, visited = collect_inventory(pages.__getitem__)
        self.assertEqual(len(visited), 3)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_missing_page_does_not_write_partial_output(self):
        adapter = CastillejaDeLaCuestaAyuntamientoAdapter('castilleja-de-la-cuesta')
        def fetch(url):
            if url.endswith('=2'):
                raise RuntimeError('source unavailable')
            return document(gallery('PLAN PARCIAL', ['memoria'], 2))
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_changed_markup_forms_and_procurement_are_not_records(self):
        for html in ['', '<h1>Acceso denegado</h1>',
                     document(gallery('Solicitud licencia', [])),
                     '<a href="licitacion.pdf">Anuncio de licitación</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_foreign_document_or_pagination_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(document(gallery('PLAN PARCIAL', ['memoria'])).replace(
                DOC_PREFIX, 'https://example.org/'))
        for href in ['https://example.org/?pagegalleryfiles-1-1=2', '?page=2', '?pagegalleryfiles-1-1=0']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                page_url(href)

    def test_stable_ids_and_disabled_licences(self):
        html = document(gallery('PLAN PARCIAL', ['memoria']))
        adapter = CastillejaDeLaCuestaAyuntamientoAdapter('castilleja-de-la-cuesta')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=html):
            out = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(out)
            before = json.loads(out.read_text())
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(before, json.loads(out.read_text()))
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('castilleja-de-la-cuesta')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CastillejaDeLaCuestaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
