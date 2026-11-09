import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.san_vicente_de_alcantara import SanVicenteDeAlcantaraAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def row(number, title, description='Documento del PGM'):
    return (f'<div>Documento| <strong>Fecha de Alta:</strong>18/04/2021 '
            f'<a href="./documentos/{number}.pdf">{title}</a>'
            f'<span>Descripción: {description}</span></div>')


ROWS = (row(1, '01. NORMAS URBANÍSTICAS') + row(2, '02. MEMORIA INFORMATIVA')
        + row(3, '03. MEMORIA JUSTIFICATIVA') + row(4, 'Plano Catálogo', 'OE-7.1'))


def page(content=ROWS):
    return '<div class="contenidop"><div id="titulo">Plan General Municipal</div>' + content + '</div>'


class ParserTests(unittest.TestCase):
    def test_one_instrument_dedup_and_dates(self):
        rows = SanVicenteDeAlcantaraAdapter.parse_inventory(page(ROWS + row(4, 'Plano Catálogo', 'OE-7.1')))
        self.assertEqual(len(rows), 1)
        record = rows[0]
        self.assertEqual(record['codigo_ine'], '06123')
        self.assertEqual(len(record['documentos']), 4)
        self.assertEqual(record['documentos'][3]['descripcion'], 'OE-7.1')
        self.assertEqual(record['documentos'][0]['url'], 'https://sanvicentedealcantara.es/documentos/1.pdf')
        self.assertEqual(record['documentos'][0]['fecha_alta'], '2021-04-18')
        for key in ['fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry']:
            self.assertIsNone(record[key])

    def test_pagination_refused(self):
        for link in ['<a href="?page=2">2</a>', '<a rel="next" href="?p=2">→</a>',
                     '<a href="?p=2">Siguiente</a>', '<div class="pagination"></div>']:
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, '[Pp]agination|pagination'):
                SanVicenteDeAlcantaraAdapter.parse_inventory(page(ROWS + link))

    def test_changed_or_irrelevant_source_refused(self):
        for html in ['<h1>Licencias: formulario de solicitud</h1>', page(''),
                     page(ROWS.replace('18/04/2021', '31/02/2021')),
                     page(ROWS + '<a href="documentos/99.pdf">Moved row</a>'),
                     page(ROWS.replace('./documentos/1.pdf', 'https://example.org/1.pdf'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                SanVicenteDeAlcantaraAdapter.parse_inventory(html)

    def test_sidebar_pdf_excluded(self):
        record = SanVicenteDeAlcantaraAdapter.parse_inventory(page() +
            '<aside><a href="documentos/99.pdf">Unrelated project</a></aside>')[0]
        self.assertEqual(len(record['documentos']), 4)

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('san-vicente-de-alcantara')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, text=page(), content=page().encode())
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.san_vicente_de_alcantara.requests.get', return_value=response) as get:
            output = Path(tmp) / 'projects.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / 'state.json')['rows'], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(json.loads(output.read_text())['id'], 'san-vicente-de-alcantara-pgm')
            get.assert_called_with(SOURCE, timeout=35, headers={'User-Agent': 'municipio-san-vicente-de-alcantara/1.0'})
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
