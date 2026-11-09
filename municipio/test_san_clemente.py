"""Offline parser/adapter contract tests; no live network in the test suite."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.san_clemente import SOURCE, SanClementeAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def section(title, links):
    return '<li><h4 class="accordion-title">' + title + '</h4><div class="accordion-content">' + links + '</div></li>'


def fixture():
    return '<ul class="accordion-items">' + ''.join([
        section('PLAN DE ORDENACIÓN MUNICIPAL - PLANOS', 'VER MODIFICACIÓN Nº 1'),
        section('MODIFICACIÓN PUNTUAL Nº 1 POM - Normas Urbanísticas',
                '<a href="/wp-content/uploads/2021/08/normas.pdf">Normas refundidas 2020</a>'),
        section('MODIFICACIÓN PUNTUAL Nº 1 POM - Planos',
                '<a href="/wp-content/uploads/mapa.pdf">Plano A</a><a href="/wp-content/uploads/mapa.pdf">Duplicado</a>'),
        section('MODIFICACIÓN PUNTUAL Nº 2 POM - Información Pública',
                '<a href="https://mega.nz/file/example#fragment">Documento refundido nº 1 y 2</a>'
                '<a href="https://www.dipucuenca.es/documents/34525/example">Publicación aprobación definitiva – BOP</a>'),
    ]) + '</ul>'


class SanClementeTests(unittest.TestCase):
    def test_grouping_and_document_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(rows[1]['documentos'][0]['url'], 'https://mega.nz/file/example#fragment')
        self.assertEqual(len(rows[0]['secciones_fuente']), 2)
        self.assertTrue(all(d['inventory_url'] == SOURCE for r in rows for d in r['documentos']))
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_dates_and_geometry_not_inferred(self):
        for row in parse_inventory(fixture()):
            self.assertEqual(row['codigo_ine'], '16190')
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob'):
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)
            self.assertNotIn('lat', row)
            self.assertFalse(row['publication_ready'])

    def test_empty_navigation_forms_or_changed_inventory_fail(self):
        for html in ('', '<a href="/plan.pdf">POM</a>',
                     '<ul class="accordion-items">' + section('Impreso de licencia', '<a href="/form.pdf">Solicitud</a>') + '</ul>',
                     fixture().replace('MODIFICACIÓN PUNTUAL Nº 2 POM', 'OTRO PLAN')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for pagination in ('<a rel="next" href="/page/2">2</a>', '<nav class="pagination">2</nav>', '<div class="page-links">2</div>'):
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(fixture() + pagination)

    def test_missing_documents_or_unreviewed_host_fail(self):
        for html in (fixture().replace('https://mega.nz/', 'https://unreviewed.example/'),
                     '<ul class="accordion-items">' + section('MODIFICACIÓN PUNTUAL Nº 3 POM - Planos', 'Sin documentos') + '</ul>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_method_contract_and_failure_preserves_output(self):
        adapter = SanClementeAyuntamientoAdapter('san-clemente')
        response = Mock(text=fixture(), url=SOURCE)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.san_clemente.requests.get', return_value=response):
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['rows'], 2)
            saved = out.read_text()
            self.assertEqual(len([json.loads(line) for line in saved.splitlines()]), 2)
            response.text = '<html>Unavailable</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), saved)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['rows'], 0)

    def test_manifest(self):
        manifest = load_manifest('san-clemente')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '16190')
        self.assertEqual(manifest.provincia, 'Cuenca')
        self.assertIsInstance(load_portal_adapter(manifest), SanClementeAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
