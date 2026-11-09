"""Offline parser and fail-closed extraction tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.castejon import CastejonAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

TITLE = ('PERIODO DE INFORMACION PUBLICA DE LA RELACION DE BIENES Y DERECHOS '
         'AFECTADOS PROYECTO ALTA VELOCIDAD')


def row(ident, title):
    return (f'<tr><td><a href="anuncio.aspx?id={ident}"></a></td>'
            f'<td>26/10/2026 - 17/11/2026</td><td>{title}</td></tr>')


def inventory(extra=''):
    return ('<select id="ddlArea"><option selected>Todas las áreas</option></select>'
            '<table class="gridview"><tr><th>Fecha</th><th>Anuncio</th></tr>'
            + row('27840', TITLE) + row('27840', TITLE)
            + row('2', 'Solicitud de licencia de obra mayor')
            + row('3', 'Licitación de obras de pavimentación')
            + row('4', 'Aprobación inicial MC 9-2026') + '</table>' + extra)


def detail():
    doc = ('<div class="adjunto"><div class="adjunto-titulo">Anuncio ADIF</div>'
           '<a href="documento.aspx?id=66181&amp;modo=guardar">Descargar</a></div>')
    return ('<div id="leer"><h2>' + TITLE + '</h2>Código de anuncio: 27840'
            '<div class="fechas-exposicion">Expuesto actualmente desde el día 26/10/2026</div>'
            + doc + doc + '</div>')


class CastejonTests(unittest.TestCase):
    def test_inventory_excludes_non_projects_deduplicates_and_dates(self):
        notices, count = CastejonAyuntamientoAdapter.parse_inventory(inventory())
        self.assertEqual(count, 5)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]['fecha_publicacion'], '2026-10-26')
        self.assertEqual(notices[0]['fecha_fin_exposicion'], '2026-11-17')
        self.assertTrue(notices[0]['url'].endswith('anuncio.aspx?id=27840'))

    def test_pagination_fails_instead_of_truncating(self):
        for pager in ('<a href="?page=2">2</a>', '<a href="javascript:__doPostBack(\'grid\',\'Page$2\')">2</a>',
                      '<button>Siguiente</button>', '<select id="pager"><option>2</option></select>'):
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'pagination'):
                CastejonAyuntamientoAdapter.parse_inventory(inventory(pager))

    def test_markup_empty_filtered_and_bad_date_fail(self):
        for html in ('<html>Unavailable</html>', inventory().replace(TITLE, 'Impreso de solicitud'),
                     inventory().replace('Todas las áreas', 'Edictos'),
                     inventory().replace('26/10/2026', '31/02/2026')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                CastejonAyuntamientoAdapter.parse_inventory(html)

    def test_documents_grouped_and_deduplicated(self):
        notice = CastejonAyuntamientoAdapter.parse_inventory(inventory())[0][0]
        docs = CastejonAyuntamientoAdapter.parse_detail(detail(), notice)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['id'], '66181')
        for html in (detail().replace('26/10/2026', '25/10/2026'),
                     detail().replace('Código de anuncio: 27840', 'Código de anuncio: 10'),
                     detail().replace('class="adjunto"', 'class="lost"'),
                     detail().replace('documento.aspx?id=66181', 'https://example.org/documento.aspx?id=66181')):
            with self.assertRaises(ValueError):
                CastejonAyuntamientoAdapter.parse_detail(html, notice)

    def test_extraction_writes_one_project_and_preserves_output_on_bad_pdf(self):
        adapter = CastejonAyuntamientoAdapter('castejon')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), detail().encode(), b'%PDF-1.7 test']):
                report = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report['rows'], 1)
            self.assertEqual(len(rows[0]['documentos']), 1)
            self.assertEqual(rows[0]['codigo_ine'], '31070')
            self.assertIsNone(rows[0]['fecha_acuerdo'])
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[0]['geometry'])
            self.assertNotIn('fecha', rows[0])
            before = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), detail().encode(), b'<html>login</html>']):
                with self.assertRaisesRegex(ValueError, 'PDF'):
                    adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_bytes(), before)

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('castejon')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CastejonAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(adapter.SOURCE, SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            with patch.object(adapter, '_fetch', side_effect=AssertionError('No licence requests')):
                self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
