"""Offline contract tests. Live sources are exercised separately in evidence/."""
import unittest

from municipio.adapters.constanti import (
    BASE, SOURCE, _action, _local, ajax_fragments, build_record,
    parse_documents, parse_index,
)

TITLE = "Projecte d'urbanització del PPU-10 (Exp. 1702/2018)"
URL = BASE + '/transparency/c052c094-04a0-4214-a410-df598e3014ea/'


def doc(title='Memòria', href=BASE + '/preview-document/test'):
    return f'<tr><td class="class_name"><a href="{href}">{title}</a></td></tr>'


class ConstantiTests(unittest.TestCase):
    def test_group_documents_and_preserve_publication_semantics(self):
        html = '<table>' + doc() + doc('Aprovació definitiva BOPT 06/08/2019', 'https://www.diputaciodetarragona.cat/ebop/example') + '</table>'
        documents, more = parse_documents(html, URL)
        row = build_record(TITLE, URL, documents, 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['fecha_publicacion'], '2019-08-06')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['expediente'], '1702/2018')
        self.assertEqual(row['codigo_ine'], '43047')
        self.assertIsNone(more)

    def test_pagination_xml_retains_added_documents(self):
        xml = '<ajax-response><component id="x"><![CDATA[<table>' + doc() + '</table>]]></component><component id="y"><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        documents, more = parse_documents(ajax_fragments(xml), URL)
        self.assertEqual(len(documents), 1)
        self.assertIsNone(more)
        with self.assertRaises(ValueError):
            ajax_fragments('<ajax-response><redirect>login</redirect></ajax-response>')

    def test_active_more_button_and_navigation(self):
        html = '''<div class="more_results"><button onclick="wicketAjaxGet('../../?x=abc',null)">Veure'n més</button></div>'''
        _, more = parse_documents(html, URL)
        self.assertEqual(_action(more, URL), BASE + '/?x=abc')

    def test_count_mismatch_never_silently_truncates(self):
        documents, _ = parse_documents('<table>' + doc() + '</table>', URL)
        with self.assertRaises(ValueError):
            build_record(TITLE, URL, documents, 13)
        # Repeated documents cannot fill a missing pagination page.
        with self.assertRaises(ValueError):
            build_record(TITLE, URL, documents * 2, 2)

    def test_announcements_alone_are_not_project(self):
        documents, _ = parse_documents('<table>' + doc('Licitació', 'https://example.org/contract') + '</table>', URL)
        with self.assertRaises(ValueError):
            build_record(TITLE, URL, documents, 1)

    def test_index_requires_named_projects_and_counts(self):
        html = f'''<div id="content">Projectes d'urbanització<table><a class="exp" onclick="wicketAjaxGet('../../?x=abc',null)">{TITLE}<span class="linkExtraInfo"> ( 13 )</span></a></table></div>'''
        folders = parse_index(html)
        self.assertEqual(folders[0][:2], (TITLE, 13))
        with self.assertRaises(ValueError):
            parse_index(html.replace(' ( 13 )', ''))
        with self.assertRaises(ValueError):
            parse_index(html.replace('</div>', '<div class="more_results"><button>More</button></div></div>'))
        with self.assertRaises(ValueError):
            parse_index('<html>Login</html>')

    def test_official_host_guard(self):
        self.assertEqual(_local(SOURCE), SOURCE)
        with self.assertRaises(ValueError):
            _local('https://example.org/transparency/')

    def test_stable_identity(self):
        documents, _ = parse_documents('<table>' + doc() + '</table>', URL)
        first = build_record(TITLE, URL, documents, 1)
        second = build_record(TITLE + ' updated', URL, documents, 1)
        self.assertEqual(first['id'], second['id'])


if __name__ == '__main__':
    unittest.main()
