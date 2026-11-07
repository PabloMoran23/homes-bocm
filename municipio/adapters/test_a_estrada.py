import unittest
from municipio.adapters.a_estrada import AEstradaAyuntamientoAdapter as A
class AEstradaTests(unittest.TestCase):
    def test_distinct_instruments_not_navigation_or_alias_duplicates(self):
        h='<a href="/urbanismo/pxom/">PXOM</a>'*3+'<a href="/urbanismo/plan-baiuca/">Plan Especial Baiuca</a><a href="/urbanismo/ordenanzas/">Ordenanzas</a>'
        self.assertEqual(len(A.discover(h)),2)
    def test_documents_grouped_and_external_forms_excluded(self):
        h='<a href="/plan.pdf">Plan</a>'*2+'<a href="https://other.es/form.pdf">Formulario</a>'
        self.assertEqual(len(A.documents(h,A.SOURCE)),1)
        with self.assertRaises(ValueError):A.discover('<h1>Error</h1>')
if __name__=='__main__':unittest.main()
