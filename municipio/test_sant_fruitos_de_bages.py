import unittest

from municipio.adapters.sant_fruitos_de_bages import (
    SantFruitosDeBagesAyuntamientoAdapter as Adapter, SOURCE, TITLE,
)


DOC = SOURCE.split('/transparency')[0] + '/preview-document/906f0d82-0204-4346-9cfe-83ba26ac802e'
LINK = f'<tr><td class="class_name"><a href="{DOC}">Certificat d’acord</a></td></tr>'
MORE = '''<div class="more_results"><button onclick="wicketAjaxGet('../../?x=public-next',null)">Veure'n més</button></div>'''


def page(body):
    return f'<div id="content">{TITLE}/Aprovació inicial<table>{body}</table></div>'


class ParserTests(unittest.TestCase):
    def test_index_declared_count_and_public_navigation(self):
        html = f'''<div id="content">{TITLE}<table class="TransparencyListPanel">
        <a class="exp" onclick="wicketAjaxGet('../../?x=folder',null)">Aprovació inicial ( 18 )</a>
        </table></div>'''
        url, count = Adapter.parse_index(html)
        self.assertEqual(count, 18)
        self.assertTrue(url.endswith('/?x=folder'))

    def test_document_group_and_unknown_dates(self):
        docs, more = Adapter.parse_document_page(page(LINK + LINK), SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertIsNone(more)
        row = Adapter.build_record(docs, 1, SOURCE)
        self.assertEqual(row['documentos'][0]['url'], DOC)
        for key in ['fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertEqual(row['fase'], 'aprobación inicial')

    def test_xml_load_more(self):
        xml = '<?xml version="1.0"?><ajax-response><component><![CDATA[' + LINK + MORE + ']]></component></ajax-response>'
        docs, more = Adapter.parse_document_page(xml, SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertTrue(more.endswith('/?x=public-next'))

    def test_refuses_truncated_inventory(self):
        docs, _ = Adapter.parse_document_page(page(LINK), SOURCE)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            Adapter.build_record(docs, 18, SOURCE)

    def test_rejects_navigation_login_and_unrelated_sources(self):
        for html in ['<h1>Login</h1>', '<a>POUM</a>', page('<a>Formulari llicència</a>'),
                     page(LINK.replace(DOC, 'https://example.org/document.pdf'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_document_page(html, SOURCE)

    def test_rejects_new_stages(self):
        html = f'<div id="content">{TITLE}<table class="TransparencyListPanel"><a class="exp">Inicial</a><a class="exp">Definitiva</a></table></div>'
        with self.assertRaisesRegex(ValueError, 'stages changed'):
            Adapter.parse_index(html)


if __name__ == '__main__':
    unittest.main()
