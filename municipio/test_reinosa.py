"""Offline parser and adapter contract checks; live evidence is kept separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.reinosa import SOURCE, ReinosaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def document(title, filename):
    return f'<a href="/wp-content/uploads/bsk-pdf-manager/{filename}.pdf">{title}</a>'


def inventory():
    return '<div class="entry-content">' + document('LICENCIA DE OBRAS', 'form') + '''
    <div id="Planifica"><div class="bsk-pdf-category cat-6">''' + (
        document('MEMORIA', 'memoria') + document('PLANOS CLASIFICACION DEL SUELO', 'planos')
    ) + '</div><div class="bsk-pdf-category cat-7">' + (
        document('MODIFICACION PUNTUAL 01', 'mp1')
        + document('MODIFICACION PUNTUAL 01', 'mp1-anexo')
        + document('MODIFICACION PUNTUAL 01', 'mp1')
        + document('MODIFICACION PUNTUAL 02 a 08', 'mp2-8')
    ) + '</div><div class="bsk-pdf-category cat-8">' + document(
        'MODIFICACION ORDENANZAS DEL PLAN PARCIAL POLIGONO INDUSTRIAL LA VEGA', 'vega'
    ) + '</div></div></div>'


class ReinosaTests(unittest.TestCase):
    def test_instruments_group_documents_and_preserve_ranges(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual([d['titulo'] for d in rows[0]['documentos']],
                         ['MEMORIA', 'PLANOS CLASIFICACION DEL SUELO'])
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertTrue(rows[2]['agrupacion_documental'])
        self.assertIn('02 a 08', rows[2]['titulo'])
        self.assertTrue(all('vega' not in d['url'] for d in rows[0]['documentos']))

    def test_no_form_dates_status_or_coordinates_inferred(self):
        rows = parse_inventory(inventory().replace('memoria.pdf', '2016-11-17_33.pdf'))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '39059')
            self.assertEqual(row['provincia'], 'Cantabria')
            self.assertFalse(row['publication_ready'])
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)
            self.assertNotIn('LICENCIA', row['titulo'])
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_missing_empty_or_changed_inventory_fails(self):
        for html in ('<html>Not found</html>', inventory().replace('cat-7', 'cat-9'),
                     inventory().replace(document('MODIFICACION PUNTUAL 02 a 08', 'mp2-8'),
                                         document('LICENCIA', 'form'))):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_unexpected_external_document_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('/wp-content/uploads/bsk-pdf-manager/memoria.pdf',
                                                 'https://example.org/memoria.pdf'))

    def test_pagination_fails_instead_of_truncating(self):
        for marker in ('<a rel="next" href="?page=2">2</a>',
                       '<div class="pagination">2</div>', '<a href="?p=2">Siguiente</a>'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                parse_inventory(inventory().replace('<div id="Planifica">',
                                                    '<div id="Planifica">' + marker))

    def test_refresh_and_error_preserve_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = ReinosaAyuntamientoAdapter('reinosa')
            response = Mock(url=SOURCE, text=inventory())
            with patch('municipio.adapters.reinosa.requests.get', return_value=response):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 4)
            saved = out.read_text()
            self.assertEqual(len([json.loads(line) for line in saved.splitlines()]), 4)
            response.text = '<html>Captcha</html>'
            with patch('municipio.adapters.reinosa.requests.get', return_value=response):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), saved)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['count'], 0)

    def test_manifest(self):
        manifest = load_manifest('reinosa')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '39059')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter,
                         'municipio.adapters.reinosa:ReinosaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
