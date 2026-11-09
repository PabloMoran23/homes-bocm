import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from municipio.adapters.casariche import CasaricheAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def inventory(body):
    return '''<article id="post-63413"><h1 class="entry-title">PBOM – Plan Básico de Ordenación Municipal</h1>
    <div class="entry-content"><h1>DOCUMENTACIÓN</h1>''' + body + '</div></article>'


DOCUMENTS = '''<h1>Fase II</h1><h4>MEMORIA</h4>
<h4><a href="http://www.casariche.es/wp-content/uploads/memoria.pdf">Descargar</a></h4>
<h4>ÍNDICE</h4><h4><a href="https://www.casariche.es/wp-content/uploads/memoria.pdf">Descargar</a></h4>
<h1>Fase III</h1><h4>PROPUESTA</h4>
<h4><a href="/wp-content/uploads/propuesta.pdf">Descargar (propuesta)</a></h4>
<h4><a href="/wp-content/uploads/anexo.pdf">Descargar (anexo I)</a></h4>
<h4>CARTOGRAFÍA</h4><h4><a href="/wp-content/uploads/cartografia.zip">Descargar</a></h4>'''


class CasaricheTests(unittest.TestCase):
    def test_instrument_grouping_provenance_and_semantics(self):
        rows = parse_inventory(inventory(DOCUMENTS))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '41026')
        self.assertEqual(len(row['documentos']), 4)
        doc = row['documentos'][0]
        self.assertTrue(doc['url_fuente'].startswith('http://'))
        self.assertEqual([r['titulo'] for r in doc['referencias']], ['MEMORIA', 'ÍNDICE'])
        self.assertEqual(row['documentos'][2]['referencias'][0], {
            'fase_documental': 'Fase III', 'titulo': 'PROPUESTA', 'enlace_texto': 'Descargar (anexo I)'})
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])

    def test_forms_news_and_unrelated_documents_excluded(self):
        extra = '''<a href="https://docs.google.com/forms/example">Cuestionario</a>
        <a href="/?p=123">Licitación</a><a href="https://example.org/wp-content/uploads/x.pdf">Otro</a>'''
        self.assertEqual(len(parse_inventory(inventory(DOCUMENTS + extra))[0]['documentos']), 4)
        with self.assertRaises(ValueError):
            parse_inventory(inventory(extra))

    def test_pagination_fails_instead_of_truncating(self):
        for pagination in ('<a rel="next" href="?page=2">2</a>',
                           '<div class="page-links"><a href="?page=2">2</a></div>',
                           '<a href="?page=2">Siguiente</a>'):
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(inventory(DOCUMENTS + pagination))

    def test_changed_or_incomplete_source_fails(self):
        for html in ('<h1>Access denied</h1>', inventory(''),
                     inventory('<h4><a href="/wp-content/uploads/a.pdf">Descargar</a></h4>'),
                     inventory(DOCUMENTS.replace('cartografia.zip', 'cartografia.exe'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    @patch('municipio.adapters.casariche.requests.get')
    def test_refresh_and_http_failure_do_not_replace_valid_output(self, get):
        response = Mock(url=SOURCE_URL, text=inventory(DOCUMENTS))
        get.return_value = response
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            adapter = CasaricheAyuntamientoAdapter('casariche')
            result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(path.read_text())['id'], 'casariche-pbom-63413')
            before = path.read_bytes()
            response.raise_for_status.side_effect = requests.HTTPError('503')
            with self.assertRaises(requests.HTTPError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('casariche')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('Casariche', 'Sevilla', '41026'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertTrue(CasaricheAyuntamientoAdapter('casariche').backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
