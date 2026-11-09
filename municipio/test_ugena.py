"""Offline parser and completeness checks for the official Ugena inventory."""
import tempfile
import unittest
from pathlib import Path
from municipio.adapters.ugena import (
    SOURCE, UgenaAyuntamientoAdapter, action_url, inventory_entries,
    make_record, official, page_content,
)

DOC = '<tr><td class="class_name"><a class="gIconLink" href="https://ugena.sedelectronica.es/preview-document/{0}">{1}</a></td></tr>'
MORE = '<div class="more_results"><button onclick="wicketAjaxGet(\'?x=next\')">Mostrar más</button></div>'
FOLDER = '<tr><td class="class_name"><a class="gIconLink exp" onclick="wicketAjaxGet(\'?x=child\')">PLANOS<span class="linkExtraInfo"> ( 2 )</span></a></td></tr>'


class UgenaTests(unittest.TestCase):
    def test_only_inventory_documents_and_folders(self):
        soup = page_content('<a href="/form">Solicitud Licencia Obra Mayor</a>' + DOC.format('a', 'MEMORIA') + FOLDER)
        docs, folders = inventory_entries(soup)
        self.assertEqual([d['titulo'] for d in docs], ['MEMORIA'])
        self.assertEqual([(n, c) for n, c, _ in folders], [('PLANOS', 2)])

    def test_xml_components_without_evaluating_script(self):
        xml = '<?xml version="1.0"?><ajax-response><evaluate>throw unsafe;</evaluate><component><![CDATA[' + DOC.format('b', 'Plano') + ']]></component></ajax-response>'
        self.assertEqual(inventory_entries(page_content(xml))[0][0]['titulo'], 'Plano')
        with self.assertRaises(ValueError):
            page_content('<?xml version="1.0"?><ajax-response><redirect>login</redirect></ajax-response>')

    def test_same_action_url_can_advance_pagination(self):
        adapter = UgenaAyuntamientoAdapter('ugena')
        responses = iter([(page_content(DOC.format('b', 'Segundo') + MORE), SOURCE),
                          (page_content(DOC.format('c', 'Tercero')), SOURCE)])
        adapter._get = lambda session, url: next(responses)
        docs = adapter._folder(None, page_content(DOC.format('a', 'Primero') + MORE), SOURCE, set())
        self.assertEqual(len(docs), 3)

    def test_repeated_page_fails(self):
        adapter = UgenaAyuntamientoAdapter('ugena')
        soup = page_content(DOC.format('a', 'Plano') + MORE)
        adapter._get = lambda session, url: (soup, SOURCE)
        with self.assertRaisesRegex(ValueError, 'Pagination stalled'):
            adapter._folder(None, soup, SOURCE, set())

    def test_folder_count_mismatch_fails(self):
        adapter = UgenaAyuntamientoAdapter('ugena')
        adapter._get = lambda session, url: (page_content(DOC.format('a', 'Plano')), SOURCE)
        with self.assertRaisesRegex(ValueError, 'Incomplete folder'):
            adapter._folder(None, page_content(FOLDER), SOURCE, set())

    def test_grouping_and_unknown_date_semantics(self):
        docs = [{'titulo': 'MEMORIA 2020', 'url': SOURCE + 'a'}, {'titulo': 'PLANOS', 'url': SOURCE + 'b'}]
        row = make_record('NNSS', SOURCE, docs, 'Normas subsidiarias')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '45176')
        for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], make_record('NNSS', SOURCE, docs[::-1], 'Normas subsidiarias')['id'])
        with self.assertRaises(ValueError):
            make_record('NNSS', SOURCE, docs + docs, 'Normas subsidiarias')

    def test_official_navigation_and_disabled_licences(self):
        with self.assertRaises(ValueError):
            official('https://example.org/transparency')
        with self.assertRaises(ValueError):
            action_url(page_content('<a href="#">Missing action</a>').a, SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = UgenaAyuntamientoAdapter('ugena').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
