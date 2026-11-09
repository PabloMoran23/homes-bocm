"""Offline parser and navigation regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from municipio.adapters.ayora import (
    SOURCE, AyoraAyuntamientoAdapter, apply_ajax, documents, folder_entries,
    instrument_record, official_url,
)
from municipio.manifest import load_manifest, load_yaml

HOST = 'https://ayora.sedelectronica.es'
FOLDER = HOST + '/transparency/test-instrument/'


def table(content):
    return '<table class="TransparencyListPanel"><tbody>' + content + '</tbody></table>'


def doc(identifier, title):
    return f'<tr><td><a class="gIconLink" href="{HOST}/preview-document/{identifier}">{title}</a></td></tr>'


class Response:
    def __init__(self, text='', headers=None, url=SOURCE):
        self.text, self.headers, self.url = text, headers or {}, url


class AyoraTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        soup = BeautifulSoup(table(doc('a', 'BORRADOR DEL PLAN') + doc('b', 'Certificado acuerdo Pleno 2024')), 'html.parser')
        row = instrument_record('7.1.1 MODIFICACIÓN PLAN PARCIAL CALDERONES', FOLDER, documents(soup, FOLDER))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['titulo'], 'MODIFICACIÓN PLAN PARCIAL CALDERONES')
        self.assertEqual(row['codigo_ine'], '46044')
        for field in ('fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], instrument_record(row['titulo'], FOLDER, row['documentos'])['id'])

    def test_deduplicates_and_scopes_document_links(self):
        soup = BeautifulSoup(doc('outside', 'Navigation') + table(doc('a', 'Plan') * 2), 'html.parser')
        self.assertEqual(len(documents(soup, FOLDER)), 1)

    def test_not_a_project(self):
        with self.assertRaises(ValueError):
            instrument_record('Modelo solicitud licencia', FOLDER, [{'url': 'form'}])
        with self.assertRaises(ValueError):
            instrument_record('Plan sin documentos', FOLDER, [])

    def test_host_guard(self):
        for url in ('https://example.org/transparency/', 'https://ayora.sedelectronica.es.evil.test/', 'http://ayora.sedelectronica.es/'):
            with self.assertRaises(ValueError):
                official_url(url)

    def test_folder_count_required(self):
        with self.assertRaises(ValueError):
            folder_entries(BeautifulSoup(table('<a class="exp">Plan</a>'), 'html.parser'))

    def test_realistic_wicket_pagination(self):
        first = table(doc('a', 'Plan')) + '<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'?x=next\')">Mostrar más</button></div>'
        ajax = '<ajax-response><component id="new"><![CDATA[' + doc('b', 'Acuerdo') + ']]></component><component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'
        adapter = AyoraAyuntamientoAdapter('ayora')
        with patch.object(adapter, '_get', side_effect=[Response(first), Response(ajax)]) as get:
            soup = adapter._page(None, FOLDER)
        self.assertEqual(len(documents(soup, FOLDER)), 2)
        self.assertEqual(get.call_count, 2)

    def test_pagination_fails_closed(self):
        for xml in ('<ajax-response/>', '<ajax-response><redirect>login</redirect></ajax-response>', '<html/>'):
            with self.assertRaises(ValueError):
                apply_ajax(BeautifulSoup(table(''), 'html.parser'), xml)

    def test_repeated_pagination_fails(self):
        first = table(doc('a', 'Plan')) + '<div class="more_results" id="more"><button onclick="wicketAjaxGet(\'?x=next\')">Mostrar más</button></div>'
        ajax = '<ajax-response><component id="new"><![CDATA[' + doc('b', 'Acuerdo') + ']]></component></ajax-response>'
        adapter = AyoraAyuntamientoAdapter('ayora')
        with patch.object(adapter, '_get', side_effect=[Response(first), Response(ajax)]):
            with self.assertRaisesRegex(ValueError, 'loop'):
                adapter._page(None, FOLDER)

    def test_live_flow_and_count_mismatch(self):
        root = BeautifulSoup('7.1. PLANEAMIENTO URBANÍSTICO' + table('<a class="exp">7.1.1 MODIFICACIÓN PLAN CALDERONES ( 2 )</a>'), 'html.parser')
        for count in (1, 2):
            adapter = AyoraAyuntamientoAdapter('ayora')
            docs = [{'url': HOST + f'/preview-document/{i}', 'titulo': 'Plan'} for i in range(count)]
            with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_page', return_value=root), patch.object(adapter, '_folder', return_value=FOLDER), patch.object(adapter, '_collect', return_value=docs):
                output = Path(tmp) / 'proyectos.jsonl'
                if count == 1:
                    with self.assertRaisesRegex(ValueError, 'count mismatch'):
                        adapter.backfill_proyectos(output)
                    self.assertFalse(output.exists())
                else:
                    result = adapter.backfill_proyectos(output)
                    self.assertEqual(result['count'], 1)
                    self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('ayora')
        self.assertEqual(manifest.provincia, 'Valencia')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46044')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = AyoraAyuntamientoAdapter('ayora').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
