import unittest
from municipio.adapters.los_alcazares import LosAlcazaresAyuntamientoAdapter as A
class LosAlcazaresTests(unittest.TestCase):
    def test_only_actual_named_building_start(self):
        p={'id':1,'date':'2025-03-13T12:42:06','link':'https://losalcazares.es/obra/',
           'title':{'rendered':'Comienzan las obras del nuevo Pabellón Deportivo de Los Alcázares'},
           'content':{'rendered':'<p>El Ayuntamiento comunica el inicio de los trabajos para construir el nuevo pabellón deportivo municipal en la parcela indicada. El proyecto comprende la nueva estructura y los equipamientos deportivos.</p>'}}
        row=A.parse_posts([p])[0];self.assertEqual(row['fecha_publicacion'],'2025-03-13');self.assertNotIn('lat',row)
        for title in ['Finalizan las obras del Pabellón','Comienzan las obras de asfaltado','Solicitud de licencia de obras','Comienzan las obras teatrales del centro']:
            p['title']['rendered']=title
            self.assertEqual(A.parse_posts([p]),[])
    def test_insufficient_source_fails(self):
        p={'title':{'rendered':'Comienzan las obras del centro cívico'},'content':{'rendered':'Sin datos'}}
        with self.assertRaises(ValueError):A.parse_posts([p])
if __name__=='__main__':unittest.main()
