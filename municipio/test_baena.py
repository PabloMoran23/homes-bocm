import unittest
from municipio.adapters.baena import parse_projects
class TestBaena(unittest.TestCase):
 def test_group_and_exclude_forms(self):
  h='<h2>Planos PGOU casco urbano de Baena</h2><a href="/1.pdf">Plano 01 DESCARGAR PDF</a><a href="/2.pdf">Plano 02 DESCARGAR PDF</a><a href="/form.pdf">Declaración responsable DESCARGAR PDF</a>'
  r=parse_projects(h);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['documentos']),2);self.assertIsNone(r[0]['fecha'])
