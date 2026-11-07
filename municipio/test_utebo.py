import unittest
from municipio.adapters.utebo import parse_projects
class TestUtebo(unittest.TestCase):
 def test_document_filter_and_dedup(self):
  h='<a href="/plan.pdf">Está publicado el Plan General de Ordenación Urbana (PGOU)</a>'
  r=parse_projects(h+h+'<a href="/form.pdf">Solicitud de licencia</a>')
  self.assertEqual(len(r),1)
  self.assertIsNone(r[0]['fecha'])
  self.assertIsNone(r[0]['lat'])
