"""Parser and pagination regressions; no network or external fixtures required."""
import unittest
from bs4 import BeautifulSoup
from municipio.adapters.palleja import SOURCE, group_projects, parse_ajax, parse_documents, _more


def board_row(key='eb34fe2a-4a5f-453d-a288-d8a8d1453ab0', title='APROVACIÓ INICIAL MTV CIRCUIT PUMPTRACK',
              description='Aprovació inicial memòria tècnica valorada circuit pumptrack',
              procedure='Actuacions Urbanístiques', code='3455/2026', publication='02/11/2026'):
    return f'''<tr><td class="class_name"><a href="https://palleja.eadministracio.cat/preview-document/{key}">{title}</a></td>
    <td class="class_folderCode">{code}</td><td class="class_folderName">{procedure}</td>
    <td class="class_description">{description}</td><td class="class_dateFrom">{publication}</td></tr>'''


def documents(html):
    return parse_documents(BeautifulSoup('<table>' + html + '</table>', 'html.parser'))


class PallejaParserTests(unittest.TestCase):
    def test_group_documents_and_date_semantics(self):
        docs = documents(board_row() + board_row('467d6084-4773-4ea5-bab2-0517b2bce227',
                         'MTV_CIRCUIT PUMPTRACK', 'Memòria tècnica valorada circuit pumptrack'))
        rows = group_projects(docs + docs)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '08157')
        self.assertEqual(row['fecha_publicacion'], '2026-11-02')
        self.assertEqual(row['fase'], 'aprobación inicial')
        for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_exclude_procurement_licences_and_unrelated_announcements(self):
        docs = documents(board_row() + board_row(procedure="Llicències d'Activitat")
                         + board_row(title='Licitació projecte circuit pumptrack')
                         + board_row(description='Pla de mesures antifrau', title='Pla administratiu'))
        self.assertEqual(len(group_projects(docs)[0]['documentos']), 1)
        with self.assertRaises(ValueError):
            group_projects(documents(board_row(procedure="Llicències d'Activitat")))

    def test_invalid_dates_and_provenance_fail(self):
        for html in (board_row(publication='31/02/2026'), board_row().replace('https://palleja.eadministracio.cat', 'https://example.com')):
            with self.assertRaises(ValueError):
                documents(html)
        with self.assertRaises(ValueError):
            group_projects(documents(board_row(code='')))

    def test_ajax_pagination_and_terminal_control(self):
        more = '''<div class="more_results"><button onclick="wicketAjaxGet('../?x=public',null)">Veure'n més</button></div>'''
        xml = '<ajax-response><component><![CDATA[<table>' + board_row() + '</table>' + more + ']]></component></ajax-response>'
        soup = parse_ajax(xml)
        self.assertEqual(len(parse_documents(soup)), 1)
        self.assertIsNotNone(_more(soup))
        with self.assertRaises(ValueError):
            _more(BeautifulSoup(more.replace("Veure'n més", 'Next'), 'html.parser'))
        terminal = parse_ajax('<ajax-response><component><![CDATA[<div class="more_results"><span></span></div>]]></component></ajax-response>')
        self.assertIsNone(_more(terminal))
        hidden = '<ajax-response><component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'
        self.assertIsNone(_more(parse_ajax(hidden, 'more')))
        with self.assertRaises(ValueError):
            parse_ajax(hidden, 'wrong-id')
        for xml in ('<html/>', '<ajax-response><redirect>login</redirect></ajax-response>',
                    '<ajax-response><component>broken</component></ajax-response>'):
            with self.assertRaises(ValueError):
                parse_ajax(xml)

    def test_identity_survives_document_order(self):
        docs = documents(board_row() + board_row('467d6084-4773-4ea5-bab2-0517b2bce227'))
        self.assertEqual(group_projects(docs), group_projects(list(reversed(docs))))

    def test_reject_navigation_only(self):
        self.assertEqual(documents('<a href="/forms">Obres</a>'), [])
        with self.assertRaises(ValueError):
            group_projects([])


if __name__ == '__main__':
    unittest.main()
