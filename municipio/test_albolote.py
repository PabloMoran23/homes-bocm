import unittest
from municipio.adapters.albolote import parse_projects
class AlboloteTests(unittest.TestCase):
    def test_excludes_theatre_keeps_physical_works(self):
        def row(n,title):return {'id':n,'title':{'rendered':title},'link':'https://albolote.org/x/','date':'2026-01-02T10:00:00'}
        rows=parse_projects([row(1,'Obra teatral'),row(2,'Comienzan obras de reforma del puente')])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['fecha_publicacion'],'2026-01-02')
        self.assertIsNone(rows[0]['fecha_aprob'])
