import unittest
from xml.sax.saxutils import escape

from municipio.adapters.villanueva_de_la_torre import (
    HOST, POM, build_record, folder_count, parse_page,
)


def link(n, title):
    return f'<a href="https://{HOST}/preview-document/00000000-0000-0000-0000-{n:012d}">{title}</a>'


def initial(body):
    return '<div>7.1. PLANEAMIENTO URBANÍSTICO/POM</div><table class="TransparencyListPanel">' + body + '</table>'


class ParserTests(unittest.TestCase):
    def test_group_documents_without_dates_or_geometry(self):
        docs, more, _ = parse_page(initial(link(1, 'MEMORIA') + link(2, 'NORMATIVA URBANISTICA')), POM, initial=True)
        row = build_record(docs, 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '19319')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertIsNone(more)
        self.assertEqual(row['id'], build_record(list(reversed(docs)), 2)['id'])

    def test_cdata_pagination_and_terminal_page(self):
        button = '<div class="more_results"><button onclick="wicketAjaxGet(\'?x=next\',null)">Mostrar más</button></div>'
        xml = '<ajax-response><component><![CDATA[' + link(3, 'PLANO') + button + ']]></component></ajax-response>'
        docs, more, _ = parse_page(xml, f'https://{HOST}/?x=previous')
        self.assertEqual(len(docs), 1)
        self.assertEqual(more, f'https://{HOST}/?x=next')
        docs, more, _ = parse_page('<ajax-response><component>' + escape(link(4, 'PLANO FINAL')) + '</component></ajax-response>', POM)
        self.assertIsNone(more)

    def test_count_is_dynamic(self):
        html = '<table class="TransparencyListPanel"><a class="exp">POM<span> ( 25 )</span></a></table>'
        self.assertEqual(folder_count(html), 25)
        with self.assertRaises(ValueError):
            folder_count(html.replace('POM', 'PAUS'))

    def test_reject_incomplete_and_duplicate_documents(self):
        docs, _, _ = parse_page(initial(link(1, 'MEMORIA') + link(2, 'NORMATIVA')), POM, initial=True)
        for batch, count in [(docs, 25), (docs + docs, 2)]:
            with self.assertRaises(ValueError):
                build_record(batch, count)

    def test_reject_login_forms_and_unrelated_news(self):
        for html in ['<h1>Identifícate</h1>', '<a>Licencia de obra mayor</a>', '<article>Noticias</article>']:
            with self.assertRaises(ValueError):
                parse_page(html, POM, initial=True)
        with self.assertRaises(ValueError):
            parse_page('<ajax-response><evaluate>login()</evaluate></ajax-response>', POM)

    def test_folder_only_page_retains_child_counts_and_actions(self):
        folder = '<a class="exp" onclick="wicketAjaxGet(&apos;?x=folder&apos;,null)">MODIFICACIÓN ORDENANZA Nº 8<span> ( 1 )</span></a>'
        # Folder entries are published after the first twenty direct documents.
        xml = '<ajax-response><component><![CDATA[' + folder + ']]></component></ajax-response>'
        docs, more, folders = parse_page(xml, POM)
        self.assertEqual(docs, [])
        self.assertIsNone(more)
        self.assertEqual(folders[0]['count'], 1)
        self.assertEqual(folders[0]['action'], POM + '?x=folder')
        with self.assertRaises(ValueError):
            parse_page(xml.replace('MODIFICACIÓN ORDENANZA Nº 8', 'LICENCIAS'), POM)

    def test_reject_external_document(self):
        html = initial(link(1, 'MEMORIA').replace(HOST, 'example.com'))
        with self.assertRaises(ValueError):
            parse_page(html, POM, initial=True)


if __name__ == '__main__':
    unittest.main()
