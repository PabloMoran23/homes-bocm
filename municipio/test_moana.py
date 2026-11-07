import unittest
from municipio.adapters.moana import parse_projects
class MoanaTests(unittest.TestCase):
    def test_inventory_requires_plan_and_groups_maps(self):
        html='<a href="/wp-content/uploads/bsk-pdf-manager/plan.pdf">PXOM MOAÑA</a><a href="/wp-content/uploads/bsk-pdf-manager/map.pdf">Solo Urbano 1</a>'
        rows=parse_projects(html)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['documentos']),2)
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertEqual(parse_projects('<a href="/service">PXOM MOAÑA</a>'),[])
