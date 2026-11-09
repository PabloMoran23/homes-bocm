import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.brion import BrionAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def inventory(extra=''):
    return '''<div><h3>PXOM</h3><p>Documentos e gráficos en formato PDF do Plan Xeral Urbanístico de Brión.</p>
    <ol><li><a href="/sites/default/files/pxom/norma.pdf">Normativa urbanística</a></li>
    <li><a href="/sites/default/files/pxom/plano.PDF">Plano de sistemas xerais</a> (Brión)</li>
    <li><a href="/sites/default/files/pxom/norma.pdf#page=2">Copia</a></li></ol>''' + extra + '</div>'


class BrionTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_facts(self):
        html = inventory() + '<a href="/formulario.pdf">Licenza</a><a href="/novas/foo">Obras</a>'
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15013')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.concellodebrion.gal/sites/default/files/pxom/norma.pdf')
        self.assertEqual(row['documentos'][1]['descripcion'], 'Plano de sistemas xerais (Brión)')
        self.assertTrue(all(d['source_url'] == SOURCE_URL for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertNotIn(key, row)

    def test_fail_closed_on_missing_section_documents_or_new_navigation(self):
        for html in ('<p>Licenza de obra</p>', inventory().replace('Normativa urbanística', 'Otro'),
                     inventory('<a href="?page=1" rel="next">Next</a>'),
                     inventory('<ul class="pager"><li><a href="?page=2">2</a></li></ul>'),
                     inventory('<a href="https://example.org/plan.pdf">Nuevo</a>'),
                     inventory().replace('Brión.', 'Otro concello.')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_path_snapshot_and_error_preserves_output(self):
        adapter = BrionAyuntamientoAdapter('brion')
        response = Mock(url=SOURCE_URL, text=inventory())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.brion.requests.get', return_value=response):
                result = adapter.backfill_proyectos(output)
                self.assertEqual(result['count'], 1)
                self.assertEqual(json.loads(output.read_text())['id'], 'brion-pxom')
                response.text = '<h1>error</h1>'
                previous = output.read_text()
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(output.read_text(), previous)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('brion')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15013')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.brion:BrionAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
