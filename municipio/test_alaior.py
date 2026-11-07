import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

from municipio.adapters.alaior import (
    AlaiorAyuntamientoAdapter, SOURCE, agreement_date, apply_page,
    official, parse_inventory, publication_date,
)
from municipio.manifest import load_manifest, load_yaml


DOC = 'https://alaior.sedelectronica.es/preview-document/example'


def table(content):
    return '<table class="TransparencyListPanel"><tbody>' + content + '</tbody></table>'


def link(url=DOC, title='Memòria'):
    return f'<tr><td><a class="gIconLink" href="{url}">{title}</a></td></tr>'


class AlaiorTests(unittest.TestCase):
    def test_manifest(self):
        manifest = load_manifest('alaior')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Alaior', 'Illes Balears', '07002'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_date_semantics(self):
        text = "Acord de Ple de data 9 de març de 2022 s'ha aprovat inicialment la revisió. Alaior, 14 de març de 2022"
        self.assertEqual(agreement_date(text), '2022-03-09')
        self.assertEqual(publication_date('BOIB 38 de data 17.03.2022 - anunci'), '2022-03-17')
        with self.assertRaises(ValueError):
            agreement_date('Alaior, 14 de març de 2022')

    def test_group_documents_not_navigation(self):
        html = table(link() + link() + '''<tr><td><a class="gIconLink exp" href="#"
            onclick="wicketAjaxGet('../../?x=public-folder',null)">PLA GENERAL ( 41 )</a></td></tr>''')
        docs, folders = parse_inventory(html, SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertEqual(folders[0]['count'], 41)
        self.assertEqual(folders[0]['titulo'], 'PLA GENERAL')

    def test_reject_shell_empty_external_and_unhandled_pagination(self):
        for html in ['<h1>Identifica’t</h1>', table(''), table(link('https://example.org/preview-document/a')),
                     table(link()) + '<a rel="next" href="?page=2">2</a>',
                     table(link()) + '<div class="more_results"><button>Veure’n més</button></div>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)
        with self.assertRaises(ValueError):
            official('http://alaior.sedelectronica.es/transparency/')

    def test_load_more_includes_later_documents(self):
        html = table(link()) + '''<div class="more_results" id="more"><button
            onclick="wicketAjaxGet('../../?x=page2',null)">Veure'n més</button></div>'''
        xml = '''<ajax-response><evaluate>THIS MUST NEVER BE EXECUTED</evaluate>
            <component id="row2"><![CDATA[''' + link(DOC + '2') + ''']]></component>
            <component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'''
        adapter = AlaiorAyuntamientoAdapter('alaior')
        with patch.object(adapter, '_get', side_effect=[(None, html), (None, xml)]):
            docs, folders = adapter._inventory(None, SOURCE)
        self.assertEqual({d['url'] for d in docs}, {DOC, DOC + '2'})
        self.assertEqual(folders, [])

    def test_load_more_rejects_empty_or_unknown_response(self):
        for xml in ['<ajax-response/>', '<html/>', '<ajax-response><component id="x"><![CDATA[<div>unknown</div>]]></component></ajax-response>']:
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                apply_page(BeautifulSoup(table(link()), 'html.parser'), xml)

    def test_repeated_pagination_fails(self):
        html = table(link()) + '''<div class="more_results" id="more"><button
            onclick="wicketAjaxGet('../../?x=page2',null)">More</button></div>'''
        xml = '<ajax-response><component id="row2"><![CDATA[' + link(DOC + '2') + ']]></component></ajax-response>'
        adapter = AlaiorAyuntamientoAdapter('alaior')
        with patch.object(adapter, '_get', side_effect=[(None, html), (None, xml)]), self.assertRaisesRegex(ValueError, 'Repeated'):
            adapter._inventory(None, SOURCE)

    def test_folder_count_mismatch_fails(self):
        adapter = AlaiorAyuntamientoAdapter('alaior')
        response = SimpleNamespace(headers={'Ajax-Location': '/transparency/child/'})
        folder = {'titulo': 'Plans', 'count': 15, 'action': 'https://alaior.sedelectronica.es/?x=folder'}
        with patch.object(adapter, '_get', return_value=(response, b'')), patch.object(adapter, '_inventory', return_value=([{'url': DOC}], [])):
            with self.assertRaisesRegex(ValueError, 'expected 15, got 1'):
                adapter._folder(None, folder, SOURCE)

    def test_two_instruments_retain_shared_documents(self):
        adapter = AlaiorAyuntamientoAdapter('alaior')
        shared = [{'titulo': 'BOIB 38 de data 17.03.2022 - anunci', 'url': DOC, 'source_url': SOURCE}]
        names = ['PLA GENERAL', "PLA D'ORDENACIÓ DETALLADA", 'INFORMES']
        folders = [{'titulo': name} for name in names]
        resolved = [(SOURCE + str(i), [{'titulo': name, 'url': DOC + str(i)}]) for i, name in enumerate(names)]
        pdf = SimpleNamespace(stdout=b"Acord de Ple de data 9 de mar\xc3\xa7 de 2022 s'ha aprovat inicialment")
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_inventory', return_value=(shared, folders)), \
                patch.object(adapter, '_folder', side_effect=resolved), \
                patch.object(adapter, '_get', side_effect=[(None, b'<iframe src="/preview/pdf/test.pdf"></iframe>'), (None, b'%PDF-test')]), \
                patch('municipio.adapters.alaior.subprocess.run', return_value=pdf):
            path = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['id'] for r in rows}), 2)
        for row in rows:
            self.assertEqual(len(row['documentos']), 3)
            self.assertEqual(row['fecha_acuerdo'], '2022-03-09')
            self.assertEqual(row['fecha_publicacion'], '2022-03-17')
            self.assertEqual(row['fase'], 'aprobación inicial')
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['fecha'])
            self.assertFalse(row['publication_ready'])


if __name__ == '__main__':
    unittest.main()
