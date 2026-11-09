"""Offline parser and traversal tests; no saved live HTML required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pravia import PraviaAyuntamientoAdapter, SECTIONS, SOURCE
from municipio.manifest import load_manifest


def page(body):
    return '<div class="journal-content-article"><div class="detalle">' + body + '</div></div>'


def inventory():
    return page(''.join(
        f'<h3><span>{heading}</span></h3><ul><li><a href="/documents/184238/{key}">Tomo 1</a></li></ul>'
        for heading, (key, _) in SECTIONS.items()
    ) + '<h3>Plusvalía</h3><a href="/documents/tax">Formulario tributario</a>')


class PraviaTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        html = inventory().replace('</ul>', '<li><a href="/documents/184238/extra">Plano</a></li><li><a href="">Plano ausente</a></li></ul>', 1)
        rows = PraviaAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['enlaces_incompletos'][0]['url'], None)
        self.assertEqual(rows[0]['documentos'][0]['source_url'], SOURCE)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '33051')
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon']:
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)
            self.assertFalse(any('tax' in d['url'] for d in row['documentos']))

    def test_reject_changed_or_paginated_inventory(self):
        for html in [page(''), inventory().replace('CATÁLOGO URBANÍSTICO', 'OTRO PLAN'),
                     inventory() + '<a href="?page=2" rel="next">2</a>',
                     inventory() + '<a href="?page=2">Siguiente</a>',
                     inventory() + '<div class="pagination">1 2</div>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                PraviaAyuntamientoAdapter.parse_inventory(html)

    def test_nested_documents_cycles_dedup_and_disabled_licences(self):
        nested_url = 'https://www.ayto-pravia.es/web/ayto-pravia/planos'
        main = inventory().replace('/documents/184238/pgo', nested_url)
        nested = page('<a href="/documents/184238/one">Plano 1</a>'
                      '<a href="/documents/184238/one">Plano 1 duplicado</a>'
                      '<a href="">Plano 2 ausente</a>'
                      f'<a href="{nested_url}">Volver</a>')
        adapter = PraviaAyuntamientoAdapter('pravia')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda u: main if u == SOURCE else nested):
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            row = json.loads(path.read_text().splitlines()[0])
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len(row['documentos']), 1)
            self.assertEqual(row['documentos'][0]['source_url'], nested_url)
            self.assertEqual(len(row['enlaces_incompletos']), 1)
            self.assertEqual(adapter.update_proyectos(path, Path(directory)/'state'), result)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
        with self.assertRaises(ValueError):
            adapter.parse_document_page(page('<a href="https://example.org/a">external</a>'), nested_url)
        with self.assertRaises(ValueError):
            adapter.parse_document_page(page('no documents'), nested_url)

    def test_manifest(self):
        manifest = load_manifest('pravia')
        self.assertEqual(manifest.provincia, 'Asturias')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.pravia:PraviaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
