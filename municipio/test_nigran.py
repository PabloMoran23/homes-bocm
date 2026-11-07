import unittest
from municipio.adapters.nigran import parse_projects
class TestNigran(unittest.TestCase):
 def test_current_link_not_forms(self):
  h='<a href="https://www.dropbox.com/new">Plan Xeral de Ordenación Municipal (Documento aprobado provisionalmente - 2026)</a><a href="/form">Solicitude</a>'
  r=parse_projects(h);self.assertEqual(len(r),1);self.assertIn('provisionalmente',r[0]['titulo']);self.assertIsNone(r[0]['fecha_aprob'])
