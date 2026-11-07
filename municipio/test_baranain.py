import unittest
from municipio.adapters.baranain import parse_projects
class BaranainTests(unittest.TestCase):
    def test_participation_is_not_approval_or_recruitment(self):
        def r(n,t):return {'id':n,'title':{'rendered':t},'link':'https://www.baranain.es/post/','date':'2024-01-01'}
        rows=parse_projects([r(1,'Plan de Participación del Plan Especial de Actuación Urbana parcela E1'),r(2,'Concurso traslado especial')])
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['fecha_aprob'])
