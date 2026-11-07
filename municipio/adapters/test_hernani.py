import unittest
from municipio.adapters.hernani import HernaniAyuntamientoAdapter as A
class HernaniTests(unittest.TestCase):
    def test_actual_notice_date_and_stable_id(self):
        h='<div class="titulo_fecha"><span class="titulo"><a href="/es/urbanismo/-/asset_publisher/abc/content/498424-241?redirect=x">PROYECTO DE REPARCELACIÓN KA.03.3</a></span><span class="fecha">02·11·2026</span></div>'
        rows=A.parse_inventory(h+h);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['fecha_publicacion'],'2026-11-02');self.assertNotIn('lat',rows[0]);self.assertNotIn('?',rows[0]['url'])
    def test_paging_or_missing_records_fails(self):
        with self.assertRaises(ValueError):A.parse_inventory('<a href="?page=2">Siguiente</a>')
        with self.assertRaises(ValueError):A.parse_inventory('<h1>Licencia</h1>')
if __name__=='__main__':unittest.main()
