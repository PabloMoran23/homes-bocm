import unittest
from municipio.adapters.burlada import BurladaAyuntamientoAdapter as A

class BurladaTests(unittest.TestCase):
    def test_only_initial_notice_and_actual_publication_date(self):
        p={'id':12,'date':'2025-02-03T12:01:00','link':'https://www.burlada.es/noticias/peau/',
           'title':{'rendered':'Plan Especial de Actuación Urbana parcela 86'},
           'content':{'rendered':'Se inicia el proceso de participación. <a href="/plan.pdf">Plan</a>'}}
        rows=A.parse_posts([p]);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['fecha_publicacion'],'2025-02-03');self.assertNotIn('lat',rows[0])
        p['content']['rendered']='Reunión de retorno <a href="/plan.pdf">Plan</a>'
        self.assertEqual(A.parse_posts([p]),[])
    def test_generic_title_uses_actual_body_heading(self):
        p={'id':15,'date':'2026-06-23T14:36:32','link':'https://www.burlada.es/noticias/peau/',
           'title':{'rendered':'¡Infórmate y participa!'},
           'content':{'rendered':'<h2>Plan especial Landazábal</h2>Se inicia el proceso de participación <a href="/p.pdf">Plan</a>'}}
        self.assertEqual(A.parse_posts([p])[0]['titulo'],'Plan especial Landazábal')

if __name__=='__main__': unittest.main()
