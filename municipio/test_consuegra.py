import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.consuegra import ConsuegraAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


HTML = '''<main><ol>
<li><a href="https://drive.google.com/file/d/text/view"><img></a>
<a href="https://drive.google.com/file/d/text/view">Normas Subsidiarias Consuegra (Texto Refundido 9/2014)</a></li>
<li><a href="https://www.dropbox.com/s/map/map.pdf?dl=0"><img></a>
<a href="https://drive.google.com/file/d/map/view">Plano Termino Municipal</a></li>
</ol></main><aside><a href="/licencia">Licencia de Obra Mayor</a></aside>'''


class ConsuegraTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = ConsuegraAyuntamientoAdapter.parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45053')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['urls']), 1)
        self.assertEqual(len(row['documentos'][1]['urls']), 2)
        self.assertEqual(row['documentos'][1]['url'], 'https://drive.google.com/file/d/map/view')
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertIsNone(row[key])

    def test_fail_closed(self):
        variants = [HTML.replace('<main>', '<main><div class="pagination">2</div>'),
                    HTML.replace('</main>', '<a rel="next" href="/page/2">2</a></main>'),
                    HTML.replace('</main>', '<a href="/page/2">Siguiente</a></main>'),
                    '<main>Licencia de Obra Mayor: formulario de solicitud</main>',
                    HTML.replace('Normas Subsidiarias Consuegra', 'Ordenanza fiscal'),
                    HTML.replace('Plano Termino Municipal', 'Normas Subsidiarias Consuegra'),
                    HTML.replace('Plano Termino Municipal', 'Licitación de servicios'),
                    HTML.replace('drive.google.com', 'example.org')]
        for html in variants:
            with self.subTest(html=html), self.assertRaises(ValueError):
                ConsuegraAyuntamientoAdapter.parse_inventory(html)

    def test_refresh_and_manifest_loading(self):
        manifest = load_manifest('consuegra')
        adapter = load_portal_adapter(manifest)
        response = Mock(text=HTML, url=SOURCE)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.consuegra.requests.get', return_value=response):
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['_entity_policy']['entity_type'], 'normativa')
            first = json.loads(out.read_text())['id']
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], first)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
