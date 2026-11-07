import unittest
from municipio.adapters.banyoles import parse_projects
class BanyolesTests(unittest.TestCase):
    def test_documents_grouped_under_project(self):
        rows=parse_projects('<div id="dnn_ctr616_HtmlModule_lblContent"><h2>PLA PARCIAL SECTOR SUD 06</h2><a href="/Portals/0/memoria.pdf">Memoria</a><a href="/Portals/0/planols.pdf">Plans</a><hr><h2>PLÀNOLS</h2></div>')
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['documentos']),2)
        self.assertIsNone(rows[0]['fecha_publicacion'])
    def test_generic_navigation_rejected(self):
        self.assertEqual(parse_projects('<h2>PLA PARCIAL</h2><a href="/Portals/0/a.pdf">PDF</a>'),[])
