import unittest
from municipio.adapters.cardedeu import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_actual_instrument_and_exclude_unrelated(self):
        rows = parse_inventory('<main><ul><li>Modificació POUM - <a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/123">Sector Can Montells</a></li><li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/cerca">Generic search</a></li></ul></main>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['titulo'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fase', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service catalogue</html>', SETTINGS['url'])
    def test_context_title_and_duplicate_exp(self):
        html = '<main><ul><li>Modificació POUM - <a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/123">Can Montells</a></li></ul></main>'
        rows = parse_inventory(html + html, SETTINGS['url'])
        self.assertEqual(rows[0]['titulo'], 'Modificació POUM - Can Montells')
        self.assertEqual(len(rows), 1)
