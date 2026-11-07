import unittest
from municipio.adapters.o_porrino import OPorrinoAyuntamientoAdapter as A
class OPorrinoTests(unittest.TestCase):
    def test_discovers_current_inventories_and_deduplicates(self):
        h='<a href="/plans/">PXOM 2003 PLANOS 1:1000</a>'*2+'<a href="/form/">Licenza</a>'
        self.assertEqual(A.inventory_urls(h),['https://oporrino.org/plans/'])
        h='<h1>PXOM 2003 PLANOS 1:1000</h1><a href="http://oporrino.org/wp-content/uploads/_doc/PXOM/1.pdf">Plano 1</a><a href="https://oporrino.org/wp-content/uploads/_doc/PXOM/1.pdf">Plano 1</a><a href="/rules.pdf">Rules</a>'
        year,docs=A.parse_inventory(h,A.SOURCE);self.assertEqual(year,'2003');self.assertEqual(len(docs),1)
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):A.inventory_urls('<h1>Error</h1>')
        with self.assertRaises(ValueError):A.parse_inventory('<h1>PXOM 2003 PLANOS</h1>',A.SOURCE)
if __name__=='__main__':unittest.main()
