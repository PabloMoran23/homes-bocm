"""Offline parser/crawler tests; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.vilallonga import (
    BASE, SOURCE, VilallongaAyuntamientoAdapter, parse_page, official_url,
)
from municipio.manifest import load_manifest, load_yaml


def link(number, title='Anexo'):
    return ('<tr><td><a class="gIconLink" href="' + BASE +
            f'/preview-document/00000000-0000-0000-0000-{number:012d}">{title}</a></td></tr>')


def more():
    return '''<div class="more_results"><button onclick="wicketAjaxGet('?x=same')">Mostrar más</button></div>'''


def page(content, extra=''):
    return '<table class="TransparencyListPanel">' + content + '</table>' + extra


def xml(content):
    return '<ajax-response><component id="rows"><![CDATA[' + content + ']]></component></ajax-response>'


class VilallongaTests(unittest.TestCase):
    def setUp(self):
        self.adapter = VilallongaAyuntamientoAdapter('vilallonga')

    def test_parser_retains_title_and_count(self):
        html = page('''<tr><td><a class="gIconLink" href="#" onclick="wicketAjaxGet('?x=f')">Modificació Pla Ampliació Sector C Industrial<span class="linkExtraInfo"> ( 41 )</span></a></td></tr>''')
        entries, control = parse_page(html)
        self.assertIsNone(control)
        self.assertEqual(entries[0]['count'], 41)
        self.assertEqual(entries[0]['titulo'], 'Modificació Pla Ampliació Sector C Industrial')

    def test_pagination_reuses_callback_but_exhausts_rows(self):
        responses = [page(link(1), more()), xml(link(2) + more()), xml(link(3) + link(3))]
        with patch.object(self.adapter, '_fetch', side_effect=[SimpleNamespace(text=x, headers={}) for x in responses]):
            entries = self.adapter._entries(None, SOURCE)
        self.assertEqual(len(entries), 3)

    def test_stalled_pagination_and_missing_table_fail(self):
        responses = [page(link(1), more()), xml(link(1) + more())]
        with patch.object(self.adapter, '_fetch', side_effect=[SimpleNamespace(text=x, headers={}) for x in responses]):
            with self.assertRaisesRegex(ValueError, 'no progress'):
                self.adapter._entries(None, SOURCE)
        for html, ajax in [('<html>Unavailable</html>', False), ('<ajax-response/>', True),
                           (page(link(1), '<a href="?p=2">Siguiente</a>'), False)]:
            with self.assertRaises(ValueError):
                parse_page(html, ajax=ajax)

    def test_nested_document_grouping_and_count_validation(self):
        folder = {'titulo': 'Estudio ambiental', 'href': '#', 'count': 2, 'onclick': ''}
        leaves, _ = parse_page(page(link(2) + link(3)))
        top, _ = parse_page(page(link(1)))
        child_url = SOURCE + 'child/'
        with patch.object(self.adapter, '_entries', side_effect=[top + [folder], leaves]), patch.object(
                self.adapter, '_folder_url', return_value=child_url):
            docs = self.adapter._documents(None, SOURCE, 3, [], set())
        self.assertEqual(len(docs), 3)
        self.assertEqual(docs[1]['carpetas'], ['Estudio ambiental'])
        self.assertEqual(docs[1]['inventory_url'], child_url)
        with patch.object(self.adapter, '_entries', return_value=top):
            with self.assertRaisesRegex(ValueError, 'Incomplete document coverage'):
                self.adapter._documents(None, SOURCE, 41, [], set())
        with self.assertRaises(ValueError):
            official_url('https://example.org/redirect')

    def test_backfill_one_instrument_and_atomic_failure(self):
        folder = {'titulo': 'Modificació Pla Ampliació Sector C Industrial', 'href': '#', 'count': 2}
        url = BASE + '/transparency/08ed6766-7d7b-4f4b-9ecf-a2bb3e12bfa5/'
        docs = [{'titulo': 'Memoria', 'url': BASE + '/preview-document/a'},
                {'titulo': 'Aprovació Ple', 'url': BASE + '/preview-document/b'}]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(self.adapter, '_entries', return_value=[folder]), patch.object(
                    self.adapter, '_folder_url', return_value=url), patch.object(self.adapter, '_documents', return_value=docs):
                result = self.adapter.backfill_proyectos(output)
            row = json.loads(output.read_text())
            self.assertEqual(result['count'], 1)
            self.assertEqual(row['codigo_ine'], '46255')
            self.assertEqual(len(row['documentos']), 2)
            self.assertNotIn('fecha_aprob', row)
            self.assertNotIn('fecha_publicacion', row)
            self.assertNotIn('lat', row)
            previous = output.read_bytes()
            with patch.object(self.adapter, '_entries', return_value=[]):
                with self.assertRaises(ValueError):
                    self.adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            self.adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('vilallonga')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46255')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
