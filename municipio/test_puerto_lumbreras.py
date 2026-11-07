import unittest
from municipio.adapters.puerto_lumbreras import parse_projects
class TestPuertoLumbreras(unittest.TestCase):
 def test_stage_and_document_grouping(self):
  h='<h1>Plan General de Ordenación Urbana de Puerto Lumbreras</h1><div class="page__content"><div class="c-content-box"><p>APROBACIÓN INICIAL</p><a href="/ayuntamiento/wp-content/uploads/a.pdf">Memoria</a><a href="/ayuntamiento/wp-content/uploads/b.pdf">Plano</a></div></div><a href="/ayuntamiento/wp-content/uploads/form.pdf">Formulario</a>'
  r=parse_projects(h);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['documentos']),2);self.assertEqual(r[0]['estado'],'APROBACIÓN INICIAL');self.assertIsNone(r[0]['fecha_aprob'])
 def test_missing_inventory_fails(self):
  with self.assertRaises(ValueError):parse_projects('<h1>Trámites</h1>')
