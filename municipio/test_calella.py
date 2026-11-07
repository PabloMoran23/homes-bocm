import unittest
from municipio.adapters.calella import parse_projects,SOURCE
class CalellaTests(unittest.TestCase):
    def test_actual_listing_and_exposure_period(self):
        row=parse_projects('<li class="article-item"><a href="'+SOURCE+'/obra.html">Urbanització carrer X</a><div class="entradeta">Període 01/01/2020 al 02/02/2020</div></li>')[0]
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIn('Període',row['descripcion'])
    def test_navigation_rejected(self):
        self.assertEqual(parse_projects('<a href="'+SOURCE+'/obra.html">Obra</a>'),[])
