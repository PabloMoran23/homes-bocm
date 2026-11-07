import unittest
from municipio.adapters.san_bartolome import parse_projects
class SanBartTests(unittest.TestCase):
    def test_formats_not_duplicate_instruments(self):
        row={'id':'1','name':'Aprobación Definitiva de plan de San Bartolomé, publicado el 16/01/2026 en BOC y 09/01/2026 en BOP','format':'HTML','url':'https://geobdp.grafcan.es/core/documentos/1547/'}
        rows=parse_projects({'success':True,'result':{'name':'planeamiento-urbanistico-de-san-bartolome','resources':[row,dict(row,format='PDF')]}})
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(len(rows[0]['fechas_publicacion']),2)
