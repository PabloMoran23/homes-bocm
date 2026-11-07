import unittest
from municipio.adapters.sant_quirze_del_valles import SantQuirzeDelVallesAyuntamientoAdapter as A
class SantQuirzeTests(unittest.TestCase):
    def test_current_inventory_filters_generic_links(self):
        h=f'<div id="content-core"><article class="newsItem"><h2 class="newsItem__title"><a href="{A.SOURCE}/pmu">Pla de Millora Urbana PMU03</a></h2><p>Aprovació inicial</p></article><article class="newsItem"><h2 class="newsItem__title"><a href="{A.SOURCE}/form">Sol·licitud de llicència</a></h2></article></div>'
        rows,n=A.parse_inventory(h);self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['fecha']);self.assertNotIn('lat',rows[0]);self.assertIsNone(n)
    def test_missing_structure(self):
        with self.assertRaises(ValueError):A.parse_inventory('<h1>Unavailable</h1>')
if __name__=='__main__':unittest.main()
