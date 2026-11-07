import unittest
from municipio.adapters.el_viso_del_alcor import parse_projects
class VisoTests(unittest.TestCase):
    def test_components_grouped_with_ancestor(self):
        html='<ul><li><p>NNSSPM 1999</p><ul><li><p>Innovación 2002</p><ul><li><p><a href="/galeriaFicheros/pgou/a.pdf">Memoria</a></p></li><li><a href="/galeriaFicheros/pgou/b.pdf">Planos</a></li></ul></li></ul></li></ul>'
        rows=parse_projects(html)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['titulo'],'NNSSPM 1999 — Innovación 2002')
        self.assertEqual(len(rows[0]['documentos']),2)
