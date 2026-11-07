import unittest
from municipio.adapters.vilassar_de_mar import VilassarDeMarAyuntamientoAdapter as A
class VilassarTests(unittest.TestCase):
    def test_groups_documents_and_keeps_month_precision_unknown(self):
        html='<ul><li>MPGOU sòl (febrer 2023)<ul><li><a href="/a.pdf">Normativa</a></li><li><a href="/b.pdf">Plànols</a></li></ul></li><li><a href="/form.pdf">Llicència obres</a></li></ul>'
        rows=A.parse_projects(html);self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['documentos']),2);self.assertIsNone(rows[0]['fecha'])
        self.assertNotIn('lat',rows[0]);self.assertNotIn('descripcion',rows[0])
    def test_layout_failure(self):
        with self.assertRaises(ValueError):A.parse_projects('<h1>Planejament</h1>')
if __name__=='__main__':unittest.main()
