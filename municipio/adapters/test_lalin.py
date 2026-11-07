import unittest
from municipio.adapters.lalin import LalinAyuntamientoAdapter as A
class LalinTests(unittest.TestCase):
    def test_named_instrument_not_generic_registry(self):
        h='<a href="https://www.xunta.gal/dog/Publicados/2016/test.html">Estudio de detalle Agro</a><a href="https://siotuga.xunta.gal">Inventario Siotuga</a>'
        rows=A.discover(h);self.assertEqual(len(rows),1)
        row=A.enrich(rows[0],'<title>DOG 193 del 10/10/2016 - Anuncio</title><div id="audioid">Ayuntamiento de Lalín. Aprobado inicialmente el estudio de detalle de Agro.</div>')
        self.assertEqual(row['fecha_publicacion'],'2016-10-10');self.assertNotIn('lat',row)
    def test_wrong_municipality_rejected(self):
        with self.assertRaises(ValueError):A.enrich({'url':'https://www.xunta.gal/x'},'<div id="audioid">Ayuntamiento de Vigo. Estudio de detalle.</div>')
if __name__=='__main__':unittest.main()
