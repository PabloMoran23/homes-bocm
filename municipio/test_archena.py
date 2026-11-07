import unittest
from municipio.adapters.archena import parse_projects
class ArchenaTests(unittest.TestCase):
    def test_bundled_publications_preserve_semantics(self):
        rows=parse_projects('<table><tr><td>ACTUACIÓN</td><td>B.O.R.M.</td></tr><tr><td>Plan Parcial X Modificación 1</td><td>01.02.2001 y 03.04.2005</td></tr></table>')
        self.assertEqual(rows[0]['fechas_publicacion'], ['2001-02-01','2005-04-03'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['lat'])
    def test_navigation_is_not_plan(self):
        self.assertEqual(parse_projects('<a>Plan Parcial</a>'), [])
