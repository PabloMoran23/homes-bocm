import unittest
from municipio.adapters.laudio import parse_projects
class TestLaudio(unittest.TestCase):
 def test_group_documents_exclude_annual_plan(self):
  h='<ul><li>Plan especial para instalaciones<ul><li><a href="/doc/urbanismo/a.pdf">Memoria</a></li><li><a href="/doc/urbanismo/b.pdf">Planos</a></li></ul></li><li><a href="/doc/plan.pdf">Plan Normativo 2026</a></li></ul>'
  r=parse_projects(h);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['documentos']),2);self.assertIsNone(r[0]['lat'])
