import unittest
from municipio.adapters.fuente_alamo_de_murcia import parse_projects
class FuenteTests(unittest.TestCase):
    def test_requires_plan_document(self):
        x={'id':1,'title':{'rendered':'Plan Parcial sector 42'},'link':'https://ayto-fuentealamo.es/p/','date':'2026-08-06'}
        self.assertEqual(parse_projects([x]),[])
        x['content']={'rendered':'<a href="https://ayto-fuentealamo.es/wp-content/p.pdf">Plan</a>'}
        rows=parse_projects([x]);self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['fecha_aprob'])
