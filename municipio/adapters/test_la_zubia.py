import unittest
from municipio.adapters.la_zubia import LaZubiaAyuntamientoAdapter as A
class LaZubiaTests(unittest.TestCase):
    def test_catalogue_not_each_document_and_excludes_navigation(self):
        h='<a href="/fiestas.pdf">Fiestas</a><div class="singlepage"><div class="entry">Catálogo de Bienes y Espacios Protegidos <a href="/mem.pdf">Memoria</a><a href="/planos.pdf">Planos</a></div></div>'
        rows=A.parse_projects(h);self.assertEqual(len(rows),1);self.assertEqual(len(rows[0]['documentos']),2);self.assertIsNone(rows[0]['fecha']);self.assertNotIn('lat',rows[0])
    def test_missing_source_content_fails(self):
        with self.assertRaises(ValueError):A.parse_projects('<h1>Planeamiento</h1>')
        with self.assertRaises(ValueError):A.parse_projects('<div class="singlepage"><div class="entry">Catálogo de Bienes y Espacios Protegidos</div></div>')
if __name__=='__main__':unittest.main()
