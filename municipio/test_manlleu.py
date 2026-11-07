import unittest
from municipio.adapters.manlleu import ManlleuAyuntamientoAdapter as Adapter

PAGE = '''<h2>El Pla d’ordenació urbanística municipal</h2>
<p>El dimecres 27 de juny de 2023, el Diari Oficial (DOGC) va publicar l’acord d’aprovació definitiva del nou POUM de Manlleu.</p>
<p>El passat 18 de gener de 2023, la Generalitat va fer l’aprovació definitiva del nou POUM.</p>
<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/277273">Registre</a>'''

class ManlleuTests(unittest.TestCase):
    def test_real_dates_and_missing_geometry(self):
        row = Adapter.parse_projects(PAGE)[0]
        self.assertEqual(row['fecha_publicacion'], '2023-06-27')
        self.assertEqual(row['fecha_aprob'], '2023-01-18')
        self.assertIsNone(row['lat'])
        self.assertIsNone(row['fecha'])
        self.assertFalse(row['publication_ready'])

    def test_navigation_or_login_shell_is_not_a_project(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects('<h2>Login</h2><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/277273">POUM</a>')

    def test_missing_date_is_not_synthesized(self):
        row = Adapter.parse_projects(PAGE.replace('27 de juny de 2023', 'data pendent'))[0]
        self.assertIsNone(row['fecha_publicacion'])

    def test_ambiguous_link_fails_closed(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects(PAGE + '<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/999999">Other</a>')
