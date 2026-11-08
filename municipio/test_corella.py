import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.corella import CorellaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest


def fixture(extra='', duplicate=''):
    return '''<h3>PLAN GENERAL MUNICIPAL</h3>
    <h4>Estrategia y Modelo de Ocupación del Territorio de Corella</h4>
    <div><a href="/wp-content/uploads/2021/12/EMOT-mayo-2016.pdf">EMOT</a></div>
    <h4>Plan Urbanístico Municipal</h4><div>
    <a href="/wp-content/uploads/2021/12/memoria.pdf">01 MEMORIA INFORMATIVA DESCRIPTIVA Y JUSTIFICATIVA</a>
    <a href="/wp-content/uploads/2021/12/normativa.pdf">01 Normativa</a>
    ''' + extra + duplicate + '''</div><h4>Licencia de obras</h4>
    <a href="/wp-content/uploads/formulario.pdf">Descargar licencia</a>
    <h4>Callejero de Corella</h4><a href="/wp-content/uploads/callejero.pdf">Plano</a>'''


class CorellaTests(unittest.TestCase):
    def test_grouping_boundaries_and_unknown_dates(self):
        rows = CorellaAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '31077')
        self.assertEqual(len(row['documentos']), 3)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertTrue(all(d['url_fuente'] == SOURCE for d in row['documentos']))

    def test_all_documents_and_duplicates(self):
        extra = ''.join(f'<a href="/wp-content/uploads/plan-{i}.pdf">Plano {i}</a>' for i in range(120))
        duplicate = '<a href="/wp-content/uploads/2021/12/normativa.pdf">01 Normativa</a>'
        rows = CorellaAyuntamientoAdapter.parse_projects(fixture(extra, duplicate))
        self.assertEqual(len(rows[0]['documentos']), 123)
        self.assertEqual(rows[0]['id'], CorellaAyuntamientoAdapter.parse_projects(fixture())[0]['id'])

    def test_reject_missing_or_changed_inventory(self):
        for html in ('<h1>Login</h1>', '<a href="normativa.pdf">01 Normativa</a>',
                     fixture().replace('<h4>Licencia de obras</h4>', ''),
                     fixture().replace('01 Normativa', 'Documento desconocido'),
                     fixture('<a href="https://other.example/doc.pdf">Documento</a>'),
                     fixture('<a href="/wp-content/uploads/doc.zip">Documento</a>'),
                     fixture('<h3>Otro instrumento</h3>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                CorellaAyuntamientoAdapter.parse_projects(html)

    def test_pagination_fails_explicitly(self):
        for pager in ('<a rel="next" href="?page=2">Más</a>', '<div class="pagination">2</div>'):
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'pagination'):
                CorellaAyuntamientoAdapter.parse_projects(fixture() + pager)

    def test_live_method_and_snapshot_update(self):
        class Response:
            url = SOURCE
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield fixture().encode()
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.corella.requests.get', return_value=Response()):
            adapter = CorellaAyuntamientoAdapter('corella')
            path = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 1)
            self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json')['rows'], 1)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            self.assertEqual(json.loads(path.read_text())['id'], 'corella-pgm')
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('corella')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.corella:CorellaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
