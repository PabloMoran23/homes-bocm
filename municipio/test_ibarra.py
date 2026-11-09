import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.ibarra import IbarraAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest

DOC = '/documents/309088/1/memoria.pdf/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def fixture():
    return f'''<div class="journal-content-article"><div class="tabs">
    <ul class="tabs-navegacion"><li><a href="#general">DATOS GENERALES</a></li>
    <li><a href="#plan">PLAN APATTA II</a></li></ul>
    <div id="general"><a href="/form.pdf">Licencia de obras</a></div>
    <div id="plan"><h2>PLAN APATTA II</h2>
    <a href="http://www.ibarra.eus{DOC}?t=1">Memoria marzo 2019</a>
    <a href="{DOC}?t=2">Memoria marzo 2019</a></div></div></div>'''


class IbarraTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_dates(self):
        rows = IbarraAyuntamientoAdapter.parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '20042')
        self.assertEqual(len(row['documentos']), 1)
        doc = row['documentos'][0]
        self.assertEqual(len(doc['enlaces_fuente']), 2)
        self.assertEqual(doc['url'], 'https://www.ibarra.eus' + DOC)
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'geometry']:
            self.assertIsNone(row[key])
        self.assertEqual(row['id'], IbarraAyuntamientoAdapter.parse_inventory(fixture().replace('?t=1', '?t=99'))[0]['id'])

    def test_fail_closed(self):
        variants = [
            '', fixture().replace('<h2>PLAN APATTA II</h2>', ''),
            fixture().replace('Memoria marzo 2019', 'Anuncio de contratación'),
            fixture().replace('</ul>', '<a href="?page=2">Siguiente</a></ul>'),
            fixture().replace('</ul>', '<a rel="next" href="?page=2">2</a></ul>'),
            fixture().replace('</ul>', '<div class="pagination">2</div></ul>'),
            fixture().replace('id="plan"', 'id="missing"'),
            fixture().replace('class="tabs"', 'class="tabs"><div id="new"><h2>PLAN NUEVO</h2></div><div'),
        ]
        for html in variants:
            with self.subTest(html=html), self.assertRaises(ValueError):
                IbarraAyuntamientoAdapter.parse_inventory(html)

    def test_manifest_and_adapter_io(self):
        manifest = load_manifest('ibarra')
        self.assertFalse(manifest.licencias.enabled)
        adapter = IbarraAyuntamientoAdapter(manifest.slug)
        response = Mock(url=SOURCE, text=fixture())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.ibarra.requests.get', return_value=response):
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state')['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['titulo'], 'PLAN APATTA II')
            response.text = ''
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(json.loads(out.read_text())['titulo'], 'PLAN APATTA II')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
