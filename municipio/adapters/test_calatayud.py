import unittest
from municipio.adapters.calatayud import CalatayudAyuntamientoAdapter as A
class CalatayudTests(unittest.TestCase):
    def test_inventory_and_grouping(self):
        h='<a href="/urbanismo/pgou">PLAN GENERAL</a>'*2+'<a href="/normativa">Normas</a>'
        self.assertEqual(A.discover(h),['https://www.calatayud.es/urbanismo/pgou'])
        h='<h1 class="titulo">Plan General</h1><a href="/admin/resources/planos/a.pdf">archivos adjuntos</a><a href="/admin/resources/planos/a.pdf">Normas</a><a href="/rules.pdf">Rules</a>'
        row=A.parse_detail(h,A.SOURCE+'/pgou');self.assertEqual(len(row['documentos']),1);self.assertEqual(row['documentos'][0]['titulo'],'Normas');self.assertIsNone(row['fecha'])
    def test_missing_docs_fails(self):
        with self.assertRaises(ValueError):A.parse_detail('<h1 class="titulo">Plan General</h1>',A.SOURCE)
if __name__=='__main__':unittest.main()
