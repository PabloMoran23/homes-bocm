import unittest
from municipio.adapters.roses import RosesAyuntamientoAdapter as A
class RosesTests(unittest.TestCase):
    def test_approval_is_not_publication_and_next_detected(self):
        h=f'<section id="content-core"><div class="tileItem"><h2 class="tileHeadline"><a href="{A.SOURCE}/plan">PLA PARCIAL TEST</a></h2><span class="description">Aprovació definitiva CTU 25.11.1998</span></div></section><span class="listingNext"><a href="?b_start=20">Next</a></span>'
        rows,next_url=A.parse_inventory(h);self.assertEqual(rows[0]['fecha_aprobacion'],'1998-11-25');self.assertIsNone(rows[0]['fecha']);self.assertNotIn('fecha_publicacion',rows[0]);self.assertTrue(next_url.endswith('?b_start=20'))
    def test_missing_structure(self):
        with self.assertRaises(ValueError):A.parse_inventory('<h1>Unavailable</h1>')
if __name__=='__main__':unittest.main()
