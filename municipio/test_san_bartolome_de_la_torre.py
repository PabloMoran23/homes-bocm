import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.san_bartolome_de_la_torre import (
    CONVENIOS_URL, GALLERY, PGOU_URL,
    SanBartolomeDeLaTorreAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(heading, documents):
    links = ''.join(f'<tr><td><a href="{href}">{title}</a></td></tr>' for title, href in documents)
    return f'<h1>{heading}</h1><div class="sg-download-gallery"><table>{links}</table></div>'


PGOU_DOCS = [
    ('Planeamiento Vigente en San Bartolomé de la Torre', GALLERY + 'Planes-de-ordenacion-urbana/PGOU/inventario.docx'),
    ('Catalogo de Bienes y Espacios Protegidos', GALLERY + 'Planes-de-ordenacion-urbana/PGOU/catalogo.pdf'),
    ('Normas Urbanísticas', GALLERY + 'Planes-de-ordenacion-urbana/PGOU/normas.pdf'),
]
PGOU = page('Plan General de Ordenación Urbana (PGOU).', PGOU_DOCS)
CONVENIO_DOC = ('Convenio urbanístico para urbanizar la Fase 1 de la UE-18 del PGOU',
                GALLERY + 'Convenios-urbanisticos/ue18.pdf')
CONVENIO = page('Convenios y actuaciones urbanísticas en ejecución.', [CONVENIO_DOC])


class InventoryTests(unittest.TestCase):
    def test_pgou_groups_all_documents_and_deduplicates(self):
        rows = parse_inventory(page('Plan General de Ordenación Urbana (PGOU).', PGOU_DOCS + PGOU_DOCS), PGOU_URL)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['codigo_ine'], '21063')
        self.assertEqual(row['provincia'], 'Huelva')
        self.assertEqual(row['id'], parse_inventory(PGOU, PGOU_URL)[0]['id'])
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])

    def test_convenio_is_named_instrument_with_source(self):
        row, = parse_inventory(CONVENIO, CONVENIOS_URL)
        self.assertIn('UE-18', row['titulo'])
        self.assertEqual(row['tipo'], 'convenio_urbanistico')
        self.assertEqual(row['url'], row['documentos'][0]['url'])
        self.assertEqual(row['inventory_url'], CONVENIOS_URL)

    def test_excludes_forms_jobs_and_unrelated_links(self):
        extras = [('Solicitud de licencia', '/forms/licencia.pdf'),
                  ('Listado de peones aspirantes', GALLERY + 'Empleo/peones.pdf'),
                  ('Otro municipio', 'https://example.org/normas.pdf')]
        html = page('Plan General de Ordenación Urbana (PGOU).', PGOU_DOCS + extras)
        html += '<footer><a href="/vivienda-turistica.pdf">Aprobación</a></footer>'
        self.assertEqual(len(parse_inventory(html, PGOU_URL)[0]['documentos']), 3)
        html = page('Convenios y actuaciones urbanísticas en ejecución.', [CONVENIO_DOC, ('Modelo de licencia', GALLERY + 'Convenios-urbanisticos/modelo.pdf')])
        self.assertEqual(len(parse_inventory(html, CONVENIOS_URL)), 1)

    def test_fail_closed_on_redesign_or_missing_docs(self):
        for html in ('<h1>Error</h1>', page('Plan General', []), page('Plan General', PGOU_DOCS[:1])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, PGOU_URL)
        with self.assertRaises(ValueError):
            parse_inventory(PGOU, 'https://example.org/')

    def test_refuses_pagination_without_truncation(self):
        for extra in ('<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Siguiente</a>', '<nav class="pagination">1 2</nav>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(PGOU + extra, PGOU_URL)

    def test_multiple_convenios_remain_separate(self):
        other = ('Convenio urbanístico para urbanizar la UE-9', GALLERY + 'Convenios-urbanisticos/ue9.pdf')
        rows = parse_inventory(page('Convenios y actuaciones', [CONVENIO_DOC, other]), CONVENIOS_URL)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertTrue(all(len(row['documentos']) == 1 for row in rows))

    def test_document_failure_preserves_previous_output(self):
        adapter = SanBartolomeDeLaTorreAyuntamientoAdapter('san-bartolome-de-la-torre')
        def fetch(url):
            if url == PGOU_URL:
                return PGOU.encode()
            if url == CONVENIOS_URL:
                return CONVENIO.encode()
            return b'<html>Not a PDF</html>'
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous\n')
            with patch.object(adapter, '_fetch', side_effect=fetch), self.assertRaises(Exception):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_manifest_loads_and_licences_disabled(self):
        manifest = load_manifest('san-bartolome-de-la-torre')
        self.assertEqual(manifest.provincia, 'Huelva')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
