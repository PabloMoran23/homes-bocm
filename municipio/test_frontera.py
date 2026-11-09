import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.frontera import (
    SOURCE, FronteraAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<div id="sp-page-builder">' + body + '</div>'


def links(body):
    return '<div class="sppb-addon-text-block">' + body + '</div>'


INVENTORY = page(links('''
<a href="/pgo.html">Plan General de Ordenación 2003</a>
<a href="/pgo.html">Plan General de Ordenación 2003</a>
<a href="/form.pdf">Solicitud de licencia</a>
<a href="/noticia.html">Licitación de obras</a>'''))
DETAIL = page('''<div class="sppb-addon-header"><h3 class="sppb-addon-title">Plan General de Ordenación 2003</h3></div>''' + links('''
<a href="/pgo/memoria.pdf">Memoria</a>
<a href="/pgo/plano.pdf">Plano</a>
<a href="/pgo/plano.pdf#p1">Plano duplicado</a>
<a href="/pgo/f11.pdf">Aprobación modificación menor unidad de actuación F-11</a>'''))


class FronteraTests(unittest.TestCase):
    def test_inventory_filters_and_deduplicates(self):
        entries = parse_inventory(INVENTORY)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['url'], 'https://www.aytofrontera.org/pgo.html')

    def test_groups_documents_separates_amendment_no_inferred_metadata(self):
        rows = parse_instrument(DETAIL, parse_inventory(INVENTORY)[0])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertIn('F-11', rows[1]['titulo'])
        self.assertEqual(rows[1]['parent_url'], rows[0]['url'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '38013')
            self.assertNotIn('fecha_aprob', row)
            self.assertNotIn('fecha_publicacion', row)
            self.assertNotIn('fase', row)
            self.assertNotIn('lat', row)
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['documentos'][0]['source_url'], rows[0]['url'])

    def test_rejects_empty_changed_and_paginated_sources(self):
        for html in ['', page('Nothing'), INVENTORY + '<a rel="next" href="?start=10">2</a>',
                     INVENTORY + '<a href="?page=2">2</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_instrument(page('No documents'), parse_inventory(INVENTORY)[0])

    def test_rejects_unexpected_origins(self):
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY.replace('/pgo.html', 'https://example.org/pgo.html'))
        with self.assertRaises(ValueError):
            parse_instrument(DETAIL.replace('/pgo/memoria.pdf', 'https://example.org/memoria.pdf'), parse_inventory(INVENTORY)[0])

    def test_manifest_adapter_snapshot_and_failure_preserves_output(self):
        manifest = load_manifest('frontera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '38013')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, FronteraAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, DETAIL]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)
            old = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, 'broken']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), old)
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
