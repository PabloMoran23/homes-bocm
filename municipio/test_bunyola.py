import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.bunyola import (
    BunyolaAyuntamientoAdapter, SOURCE, ajax_html, make_record, parse_page,
)
from municipio.manifest import load_manifest

DOC = 'https://bunyola.sedelectronica.es/preview-document/6485432e-0230-4325-9006-d04d6fe57d45'


class BunyolaTests(unittest.TestCase):
    def test_listing_folder_count_and_documents(self):
        entries, more = parse_page(f'''<a class="gIconLink exp" onclick="wicketAjaxGet('x')">Modificació UA-1<span> ( 4 )</span></a>
            <a class="gIconLink" href="{DOC}">Documentació escrita i gràfica</a>
            <button onclick="wicketAjaxGet('next')">Veure'n més</button>''')
        self.assertEqual(entries[0]['title'], 'Modificació UA-1')
        self.assertEqual(entries[0]['count'], 4)
        self.assertEqual(entries[1]['url'], DOC)
        self.assertIsNotNone(more)

    def test_ajax_components_and_terminal_pagination(self):
        html = ajax_html('''<ajax-response><component id="a"><![CDATA[<a class="gIconLink" href="%s">Normes</a>]]></component><component id="b"><![CDATA[<div style="display:none"></div>]]></component></ajax-response>''' % DOC)
        entries, more = parse_page(html)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(more)
        for text in (' ', '<ajax-response><redirect>login</redirect></ajax-response>'):
            with self.assertRaises((ValueError, ET.ParseError)):
                ajax_html(text)

    def test_provenance_grouping_and_no_invented_dates(self):
        doc = {'titulo': 'Plànol 1982', 'url': DOC, 'inventory_url': SOURCE}
        row = make_record('PGOU', SOURCE, [doc, doc])
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['codigo_ine'], '07010')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fase', row)

    def test_reject_unrecognized_document_or_pagination(self):
        for html in ('<a rel="next" href="x">Next</a>',
                     '<a class="gIconLink" href="https://example.org/a.pdf">Normes</a>',
                     '<a class="gIconLink exp">Folder without count</a>'):
            with self.assertRaises(ValueError):
                parse_page(html)

    def test_folder_count_mismatch_fails(self):
        adapter = BunyolaAyuntamientoAdapter('bunyola')
        entries, _ = parse_page('''<a class="gIconLink exp" onclick="wicketAjaxGet('../../?x=public')">UA-1 ( 4 )</a>''')
        class Response:
            headers = {'Ajax-Location': '../../transparency/3d2792c0-4cd7-45cc-bfa7-bee30b8bcece/'}
        with patch.object(adapter, '_get', return_value=Response()), patch.object(adapter, '_inventory', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                adapter._folder(entries[0])

    def test_all_pages_traversed(self):
        adapter = BunyolaAyuntamientoAdapter('bunyola')
        class Response:
            def __init__(self, text): self.text = text
        first = f'''NORMATIVA URBANÍSTICA VIGENT <a class="gIconLink" href="{DOC}">Normes</a><button onclick="wicketAjaxGet('../../?x=page2')">Veure'n més</button>'''
        second_doc = DOC.replace('6485432e', '7485432e')
        second = f'''<ajax-response><component id="row"><![CDATA[<a class="gIconLink" href="{second_doc}">Plànol</a>]]></component></ajax-response>'''
        with patch.object(adapter, '_get', side_effect=[Response(first), Response(second)]) as fetch:
            self.assertEqual(len(adapter._inventory(SOURCE)), 2)
            self.assertEqual(fetch.call_count, 2)
        repeated = second.replace(second_doc, DOC)
        with patch.object(adapter, '_get', side_effect=[Response(first), Response(repeated)]):
            with self.assertRaisesRegex(ValueError, 'Repeated'):
                adapter._inventory(SOURCE)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('bunyola')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            BunyolaAyuntamientoAdapter('bunyola').backfill_licencias(path)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
