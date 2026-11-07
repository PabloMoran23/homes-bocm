import unittest
from municipio.adapters.lasarte_oria import parse_projects
class LasarteTests(unittest.TestCase):
    def test_requires_real_document_and_groups_components(self):
        self.assertEqual(parse_projects('<h2>Normas subsidiarias</h2>'),[])
        rows=parse_projects('<div class="destacado_contenido"><h2>Normas subsidiarias</h2><a href="/documents/298010/3842483/a">Normas Generales</a><a href="/documents/298010/3842483/b">Ficha A5</a></div>')
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['documentos']),2)
        self.assertIsNone(rows[0]['fecha_aprob'])
