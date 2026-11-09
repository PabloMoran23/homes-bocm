"""Offline contract tests; live source captures are kept outside source control."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.andorra import AndorraAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml

ROOT = 'http://www.ayuntamientoandorra.es/wp-content/uploads/sites/118/2016/06/'


def page(extra=''):
    return '''<div role="main"><h1>PLAN GENERAL DE ORDENACIÓN URBANA</h1>
<p>Ayuntamiento de Andorra (Teruel)</p></div>''' + extra


def link(name, title):
    return f'<a href="{ROOT}{name}.pdf">{title}</a>'


FIXTURE = page(
    '<p>' + link('grid', 'CUADRÍCULAS PGOU 2007') + '</p>'
    '<p>' + link('norms', 'NORMAS URBANÍSTICA PGOCU2007') + '</p>'
    '<p>' + link('mod2', 'APROVECHAMIENTO MEDIO Mod2(2008-07-30)') +
    link('grid', 'PGOU 2007') + '</p>'
    '<h3>MODIFICACIÓN PUNTUAL Nº 4</h3><p>' + link('memory', 'Memoria justificativa') + '</p>'
    '<p>' + link('map', 'No urbanizable. Hoja A1') + link('map', 'Hoja A1') + '</p>'
    '<p>Modelo solicitud licencia <a href="/solicitud">Solicitud</a></p>'
)


class AndorraTests(unittest.TestCase):
    def test_groups_documents_without_cross_contamination(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 2])
        self.assertEqual(rows[2]['titulo'], 'MODIFICACIÓN PUNTUAL Nº 4')
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('/mod2.pdf'))
        self.assertEqual(rows[0]['documentos'][0]['source_url'], ROOT + 'grid.pdf')
        self.assertTrue(rows[0]['documentos'][0]['url'].startswith('https://'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in parse_inventory(FIXTURE)])

    def test_no_inferred_dates_phase_or_geometry(self):
        for row in parse_inventory(FIXTURE):
            self.assertEqual(row['codigo_ine'], '44025')
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_reject_empty_wrong_identity_pagination_and_unknown_document(self):
        for html in ('', page(), FIXTURE.replace('(Teruel)', '(Lleida)'),
                     FIXTURE + '<a rel="next" href="?page=2">2</a>',
                     FIXTURE.replace('<h3>MODIFICACIÓN PUNTUAL Nº 4</h3>', ''),
                     FIXTURE.replace('www.ayuntamientoandorra.es', 'example.org')):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_writes_snapshot_and_disables_licences(self):
        class Response:
            url = SOURCE
            text = FIXTURE
            content = FIXTURE.encode()
            headers = {'Content-Type': 'text/html; charset=utf-8'}
            def raise_for_status(self):
                pass
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.andorra.requests.get', return_value=Response()):
            path = Path(d) / 'projects.jsonl'
            adapter = AndorraAyuntamientoAdapter('andorra')
            self.assertEqual(adapter.update_proyectos(path, Path(d)/'state')['rows'], 3)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 3)
            adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('andorra')
        self.assertEqual(manifest.provincia, 'Teruel')
        self.assertFalse(manifest.licencias.enabled)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '44025')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
