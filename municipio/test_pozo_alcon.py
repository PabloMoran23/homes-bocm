import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from municipio.adapters.pozo_alcon import (
    SOURCE, PozoAlconAyuntamientoAdapter, apply_ajax, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

TITLE = 'Información pública del Proyecto de Ejecución de la obra "Adecuación de intersección JA-8201"'


def row(description=TITLE, doc='11111111-1111-1111-1111-111111111111', date='22/10/2026'):
    return f'''<tr><td class="class_description">{description}</td>
    <td class="class_folderCode">3938/2026</td>
    <td class="class_dateFrom">{date}</td><td class="class_name">
    <a href="https://pozoalcon.sedelectronica.es/preview-document/{doc}">Documento</a></td></tr>'''


def board(rows):
    return '<table><tbody>' + rows + '</tbody></table>'


class PozoAlconTests(unittest.TestCase):
    def test_semantics_and_grouping(self):
        rows = parse_inventory(board(row() + row(doc='22222222-2222-2222-2222-222222222222') + row()))
        self.assertEqual(len(rows), 1)
        record = rows[0]
        self.assertEqual(len(record['documentos']), 2)
        self.assertEqual(record['fecha_publicacion'], '2026-10-22')
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertIsNone(record['fecha_aprob'])
        self.assertIsNone(record['geometry'])
        self.assertEqual(record['fase'], 'información pública')
        self.assertEqual(record['codigo_ine'], '23070')
        self.assertEqual(record['id'], parse_inventory(board(row()))[0]['id'])

    def test_exclusions(self):
        for text in ['ANUNCIO DE LICITACIÓN OBRA DE REPARACIÓN DE PAVIMENTO',
                     'Solicitud de licencia de obras', 'APROBACIÓN DE BASES DE EMPLEO',
                     'Información pública del Proyecto de actividades deportivas',
                     'COMUNICACIÓN DE CORTE AL TRÁFICO']:
            self.assertEqual(parse_inventory(board(row(description=text))), [])

    def test_invalid_provenance(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Identifícate</html>')
        with self.assertRaises(ValueError):
            parse_inventory(board(row(date='31/02/2026')))
        with self.assertRaises(ValueError):
            parse_inventory(board(row().replace('pozoalcon.sedelectronica.es', 'example.com')))

    def test_live_path_paginates_before_writing(self):
        first = board(row(description='Empleo')) + '''<div class="more_results" id="more">
        <button onclick="wicketAjaxGet('?x=test')">Mostrar más</button></div>'''
        last = f'''<ajax-response><component id="new"><![CDATA[{row()}]]></component>
        <component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'''
        class Response:
            def __init__(self, text):
                self.text, self.url = text, SOURCE
            def raise_for_status(self):
                pass
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.pozo_alcon.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.get.side_effect = [Response(first), Response(last)]
            output = Path(directory) / 'out.jsonl'
            result = PozoAlconAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(result['pages'], 2)
            self.assertEqual(result['board_rows'], 2)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(json.loads(output.read_text())['fase'], 'información pública')
            self.assertEqual(session.get.call_count, 2)

    def test_broken_pagination_fails(self):
        soup = BeautifulSoup(board(row()) + '<div id="more"></div>', 'html.parser')
        for payload in ['<ajax-response/>', '<ajax-response><redirect>/login</redirect></ajax-response>', ' ']:
            with self.assertRaises((ValueError, ET.ParseError)):
                apply_ajax(soup, payload, 'more')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('pozo-alcon')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('23070', 'Jaén'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
