import unittest
from municipio.adapters.torredembarra import parse_projects
class TestTorredembarra(unittest.TestCase):
 def test_group_current_instrument_documents(self):
  h='<main><h1>Avanç de POUM</h1><a href="/sites/default/files/a.pdf">Diagnosi</a><a href="/sites/default/files/b.pdf">Participació</a></main>'
  r=parse_projects(h);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['documentos']),2);self.assertIsNone(r[0]['fecha_aprob']);self.assertIsNone(r[0]['lat'])
 def test_reject_generic_page(self):
  with self.assertRaises(ValueError):parse_projects('<main><h1>Tràmits</h1></main>')

 def test_drupal_list_heading_stage(self):
  h='<main><h1>Avanç de POUM</h1><div><ul><li><p><strong>En quin punt ens trobem de la redacció?</strong></p></li></ul><p>Finalitzada la diagnosi; encara sense propostes concretes.</p><p>Participació oberta.</p></div><a href="/sites/default/files/a.pdf">Diagnosi</a></main>'
  self.assertEqual(parse_projects(h)[0]['descripcion'], 'Finalitzada la diagnosi; encara sense propostes concretes. Participació oberta.')
