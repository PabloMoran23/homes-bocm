import unittest
from municipio.adapters.huercal_overa import HuercalOveraAyuntamientoAdapter as A
class HuercalTests(unittest.TestCase):
    def test_scoped_inventory(self):
        h='<a href="?p=huercal-overa&amp;documentId=ABC">Consulta pública innovación nº23 del PGOU</a><a href="?p=huercal-overa&amp;documentId=DEF">Consulta pública ordenanza fiscal</a>'
        self.assertEqual(list(A.discover(h)),['ABC'])
    def test_real_documents_and_instrument_identity(self):
        h='<h2>Consulta pública innovación nº 23 del PGOU</h2><form class="xspForm"><a href="/ABC/$file/plan.pdf">Avance</a></form><a href="/XYZ/$file/p.pdf">Política calidad</a>'
        key,row=A.parse_detail(h,A.SOURCE,'ABC');self.assertEqual(key,'innovacion-23');self.assertEqual(len(row['documentos']),1);self.assertIsNone(row['fecha']);self.assertNotIn('lat',row)
        with self.assertRaises(ValueError):A.parse_detail('<h2>PGOU</h2>',A.SOURCE,'ABC')
if __name__=='__main__':unittest.main()
