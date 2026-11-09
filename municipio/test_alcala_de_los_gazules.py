import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.alcala_de_los_gazules import (
    SOURCE, AlcalaDeLosGazulesAyuntamientoAdapter, all_items_url,
    extract_projects, parse_inventory,
)
from municipio.manifest import load_manifest

TITLE = 'AVANCE Y DOCUMENTO INICIAL ESTRATEGICO PGOU ALCALA DE LOS GAZULES. FEBRERO 2020'
VOLUME = 'VOLUMEN I MEMORIA FEBRERO 2020'
CHILD = SOURCE + '/8-volumen-i-memoria-febrero-2020'


def page(title, docs, children=''):
    links = ''.join(f'<div class="pd-filename"><a href="?download={i}:documento">{name}</a></div>' for i, name in docs)
    return (f'<div id="phoca-dl-category-box"><h3 class="pd-ctitle">{title}</h3>{children}{links}'
            '<select name="limit"><option selected value="0">All</option></select></div>')


def pages(count=1):
    child = f'<div class="pd-subcategory"><a href="{CHILD}">{VOLUME}</a><small>({count})</small></div>'
    return {all_items_url(SOURCE): page(TITLE, [(7, 'PORTADA')], child),
            all_items_url(CHILD): page(VOLUME, [(5, 'MEMORIA URBANISTICA')])}


class InventoryTests(unittest.TestCase):
    def test_groups_documents_and_preserves_provenance(self):
        rows = extract_projects(pages().__getitem__)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '11001')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['inventory_url'], all_items_url(CHILD))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], extract_projects(pages().__getitem__)[0]['id'])

    def test_count_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            extract_projects(pages(2).__getitem__)

    def test_pagination_cannot_be_silently_truncated(self):
        for html in (page(VOLUME, []).replace('value="0"', 'value="20"'),
                     page(VOLUME, []).replace('</div>', '<div class="pagination"><a href="?start=20">Next</a></div></div>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, all_items_url(CHILD))

    def test_external_document_rejected(self):
        html = page(VOLUME, [(5, 'MEMORIA')]).replace('?download=5:documento', 'https://example.org/?download=5:documento')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            parse_inventory(html, all_items_url(CHILD))

    def test_changed_instrument_or_empty_source_rejected(self):
        source = pages()
        source[all_items_url(SOURCE)] = source[all_items_url(SOURCE)].replace(TITLE, 'Solicitud licencia de obras')
        with self.assertRaises(ValueError):
            extract_projects(source.__getitem__)
        with self.assertRaises(ValueError):
            parse_inventory('<html>Access denied</html>', SOURCE)

    def test_duplicate_document_across_volumes_rejected(self):
        source = pages()
        source[all_items_url(CHILD)] = page(VOLUME, [(7, 'PORTADA')])
        with self.assertRaisesRegex(ValueError, 'repeated'):
            extract_projects(source.__getitem__)

    def test_failed_extraction_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            out.write_text('prior snapshot')
            with patch('municipio.adapters.alcala_de_los_gazules.extract_projects', side_effect=ValueError('bad source')):
                with self.assertRaises(ValueError):
                    AlcalaDeLosGazulesAyuntamientoAdapter('alcala-de-los-gazules').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'prior snapshot')

    def test_manifest_and_licences_disabled(self):
        manifest = load_manifest('alcala-de-los-gazules')
        self.assertEqual(manifest.provincia, 'Cádiz')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licencias.jsonl'
            result = AlcalaDeLosGazulesAyuntamientoAdapter(manifest.slug).backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
