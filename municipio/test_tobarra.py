import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from municipio.adapters.tobarra import SOURCE, TobarraAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def inventory():
    sections = []
    for group, filename in [('D1 M1', 'Doc1-Memoria-informativa.pdf'),
                            ('D2 PI', 'INF-01.pdf'),
                            ('D3 MJ', 'Doc3-Memoria-Justificativa.pdf'),
                            ('D4 PO', 'OE-1.pdf'),
                            ('D5 NNUU', 'Doc5-Normas-Urbanisticas.pdf'),
                            ('D6 CAT', 'Doc6-CAT.pdf')]:
        sections.append(f'<div class="elementor-accordion-item"><a class="elementor-accordion-title">{group}</a>'
                        f'<a href="http://tobarra.es/wp-content/uploads/2024/03/{filename}">Plan de Ordenación Municipal</a></div>')
    return '<main><h1>Áreas Municipales – Urbanismo</h1>' + ''.join(sections) + '<a href="/urbanismo-tomo-i-ord-estructural">TOMO I</a><a href="/urbanismo-tomo-ii-ord-estructural">TOMO II</a></main>'


CHILD = '<main><h1>Urbanismo – TOMO I</h1><a href="/wp-content/uploads/2024/03/extra.pdf">Plan de Ordenación Municipal</a></main>'


def response(url, body, status=200):
    r = requests.Response()
    r.url, r.status_code, r._content = url, status, body.encode()
    return r


class TobarraTests(unittest.TestCase):
    def test_all_sections_and_original_provenance(self):
        docs, children = parse_inventory(inventory())
        self.assertEqual(len(docs), 6)
        self.assertEqual(len(children), 2)
        self.assertEqual(docs[0]['seccion'], 'D1 M1')
        self.assertTrue(docs[0]['url'].startswith('https://'))
        self.assertTrue(docs[0]['url_enlace_original'].startswith('http://'))
        self.assertEqual(docs[0]['source_url'], SOURCE)

    def test_forms_and_changed_structure_rejected(self):
        for html in ['<main><h1>Impresos</h1><a href="/licencia.pdf">Solicitud licencia de obras</a></main>',
                     inventory().replace('D6 CAT', 'D7 NUEVO'), '<html>Login</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for extra in ['<a rel="next" href="?page=2">2</a>', '<div class="page-links">1 2</div>',
                      '<main><h1>Urbanismo</h1><a href="?page=2">Siguiente</a></main>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(extra + inventory())

    def test_external_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('http://tobarra.es/wp-content', 'https://example.org/wp-content'))

    @patch.object(TobarraAyuntamientoAdapter, '_fetch')
    def test_live_shape_grouped_gaps_dates_and_updates(self, fetch):
        def fake(session, url):
            if url == SOURCE:
                return response(url, inventory())
            return response(url, CHILD, 404 if 'tomo-ii' in url else 200)
        fetch.side_effect = fake
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            adapter = TobarraAyuntamientoAdapter()
            result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            row = json.loads(path.read_text())
            self.assertEqual(len(row['documentos']), 7)
            self.assertEqual(len(row['limitaciones']), 1)
            self.assertEqual(row['inventarios_relacionados'][1]['http_status'], 404)
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
                self.assertIsNone(row[key])
            self.assertEqual(row['codigo_ine'], '02074')
            self.assertFalse(row['publication_ready'])

    @patch.object(TobarraAyuntamientoAdapter, '_fetch')
    def test_server_error_preserves_previous_snapshot(self, fetch):
        fetch.side_effect = lambda session, url: response(url, inventory() if url == SOURCE else 'error', 200 if url == SOURCE else 503)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaises(requests.HTTPError):
                TobarraAyuntamientoAdapter().backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tobarra')
        self.assertEqual(manifest.nombre, 'Tobarra')
        self.assertEqual(manifest.provincia, 'Albacete')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = TobarraAyuntamientoAdapter().backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
