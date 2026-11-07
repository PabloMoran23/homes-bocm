"""Offline semantic and failure-mode tests for the municipal planning inventory."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.abaran import AbaranAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def document(label, filename):
    return f'<a href="/wp-content/uploads/2026/02/{filename}">{label}</a>'


def inventory(extra=''):
    return '<div class="elementor-text-editor">' + (
        '<h2>Catálogo, Memoria y Normas urbanísticas</h2>'
        + document('Memoria', 'memoria.pdf')
        + '<h2>Modificaciones del Plan General</h2>'
        + document('Modificación número 25 1/2', 'mod25-1.zip')
        + document('Modificación número 25 2/2', 'mod25-2.zip')
        + document('Publicación BORM Modif. núm. 25', 'borm25.pdf')
        + document('Modificación número 28', 'mod28.pdf')
        + '<h2>Planos PGMOU Abarán</h2>'
        + document('Plano Guía', 'guia.pdf')
        + document('Descarga', 'guia.pdf') + extra + '</div>')


class AbaranTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        rows = parse_inventory(inventory())
        self.assertEqual([len(r['documentos']) for r in rows], [2, 3, 1])
        self.assertEqual(rows[1]['id'], 'abaran-pgmo-modificacion-25')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '30002')
            self.assertFalse(row['publication_ready'])
            self.assertFalse(any(k.startswith('fecha') or k in {'lat', 'lon', 'geometry'} for k in row))
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        moved = parse_inventory(inventory().replace('2026/02', '2027/03'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in moved])

    def test_rejects_pagination_empty_and_unknown_documents(self):
        for html in ('<p>Solicitud de licencia</p>', inventory('<a rel="next" href="?page=2">2</a>'),
                     inventory('<div class="pagination"><a href="?page=2">2</a></div>'),
                     inventory(document('External', 'form.doc')),
                     inventory().replace('Modificación número 28', 'Anuncio de contratación'),
                     inventory().replace('Planos PGMOU Abarán', 'Nueva sección')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_live_fetch_contract_and_disabled_licences(self):
        response = Mock(url=SOURCE, text=inventory())
        adapter = AbaranAyuntamientoAdapter('abaran')
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.abaran.requests.get', return_value=response) as get:
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 3)
            get.assert_called_once()
            response.raise_for_status.assert_called_once()
            self.assertEqual(adapter.backfill_licencias(path)['count'], 0)
            self.assertEqual(path.read_text(), '')
            response.url = 'https://example.org/'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)

    def test_manifest(self):
        manifest = load_manifest('abaran')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('30002', 'Abarán', 'Murcia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.abaran:AbaranAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
