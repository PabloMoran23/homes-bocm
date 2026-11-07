"""Offline parser and extraction regression tests. Run with unittest."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sonseca import SOURCE, SonsecaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml

TITLE = 'NORMAS SUBSIDIARIAS DE PLANEAMIENTO URBANÍSTICO DE SONSECA'
PDF = 'https://sonseca.es/wp-content/uploads/2021/03/nnss.pdf'


def card(title=TITLE, urls=(PDF,)):
    return ('<div class="nectar-hor-list-item"><div class="nectar-list-item">' + title +
            '</div><div class="nectar-list-item">' +
            ''.join(f'<a href="{url}">Descargar</a>' for url in urls) + '</div></div>')


class SonsecaTests(unittest.TestCase):
    def test_real_capture_structure_and_exclusions(self):
        html = card() + card('Solicitud licencia de obras') + card('TASA POR EXPEDICIÓN DE LICENCIAS URBANÍSTICAS')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45163')
        self.assertEqual(row['url_documento'], PDF)
        self.assertEqual(row['inventory_url'], SOURCE)
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_group_documents_and_stable_instrument_id(self):
        second = PDF.replace('nnss.pdf', 'planos.pdf')
        rows = parse_inventory(card() + card(urls=(PDF, second)))
        self.assertEqual(len(rows), 1)
        self.assertEqual([d['url'] for d in rows[0]['documentos']], [PDF, second])
        self.assertEqual(rows[0]['id'], parse_inventory(card(urls=(second,)))[0]['id'])

    def test_fail_closed(self):
        for html in ('<html>Access denied</html>', card('Solicitud licencia de obras'),
                     card(urls=()), card(urls=('https://example.org/nnss.pdf',)),
                     card() + '<a rel="next" href="?page=2">Siguiente</a>',
                     card() + '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_path_fetches_documents_and_refreshes_snapshot(self):
        adapter = SonsecaAyuntamientoAdapter()
        responses = [(card().encode(), SOURCE, 'text/html'), (b'%PDF-1.4 fixture', PDF, 'application/pdf')]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('stale\n')
            with patch.object(adapter, '_fetch', side_effect=responses):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['live_records'], 1)
            row = json.loads(output.read_text())
            self.assertEqual(row['documentos'][0]['bytes'], len(b'%PDF-1.4 fixture'))
            self.assertIn(PDF, result['source_urls'])
            with patch.object(adapter, '_fetch', side_effect=[responses[0], (b'blocked', PDF, 'text/html')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(json.loads(output.read_text())['id'], row['id'])

    def test_manifest_and_licences_disabled(self):
        manifest = load_manifest('sonseca')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Sonseca', 'Toledo', '45163'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = SonsecaAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
