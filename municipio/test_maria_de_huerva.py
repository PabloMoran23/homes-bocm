import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.maria_de_huerva import (
    MariaDeHuervaAyuntamientoAdapter, SOURCE, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return '''<h1>PGOU</h1><nav><a href="/unrelated.pdf">Obras</a></nav>
    <div id="wpb-content-root"><h2>Plan General de Ordenación Urbana</h2>
    <a href="/wp-content/uploads/fichas.pdf">Fichas de Ordenación</a>
    <a href="/wp-content/uploads/normas.pdf">Normas Urbanísticas</a>
    <a href="/wp-content/uploads/normas.pdf">Normas Urbanísticas</a>
    <a href="/wp-content/uploads/plano.pdf">6-1 Red de saneamiento</a>
    <h2>Catálogo de Protección</h2>
    <a href="/wp-content/uploads/catalogo.pdf">Catálogo de Protección (parte 1)</a>
    <time>2024-03-01</time></div>'''


class ParserTests(unittest.TestCase):
    def test_groups_plan_and_catalogue_excludes_navigation_and_deduplicates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['codigo_ine'], '50163')
        self.assertEqual(row['documentos'][-1]['seccion'], 'Catálogo de Protección')
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])

    def test_fails_closed_on_missing_content_or_core_documents(self):
        for html in ('<h1>Solicitud de licencia</h1>', fixture().replace('Normas Urbanísticas', 'Solicitud de licencia')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_rejects_pagination_and_foreign_documents_or_redirect(self):
        for html in (fixture().replace('<time>', '<a rel="next" href="?page=2">Next</a><time>'),
                     fixture().replace('/wp-content/uploads/plano.pdf', 'https://example.com/plano.pdf')):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_inventory(fixture(), 'https://example.com/')

    def test_manifest_and_live_method_wiring(self):
        manifest = load_manifest('maria-de-huerva')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '50163')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MariaDeHuervaAyuntamientoAdapter)
        response = Mock(text=fixture(), url=SOURCE, content=fixture().encode())
        with TemporaryDirectory() as directory, patch('municipio.adapters.maria_de_huerva.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            stats = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(stats['count'], 1)
            self.assertEqual(json.loads(output.read_text())['id'], 'maria-de-huerva-pgou')
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
