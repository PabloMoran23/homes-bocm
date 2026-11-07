import unittest
from municipio.adapters.sant_celoni import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_actual_instrument_and_exclude_unrelated(self):
        rows = parse_inventory('<div id="cos"><strong>Estatuts Associació</strong><a href="/ARXIUS/documents/statutes.pdf">Statutes</a><strong>Projecte de reparcel·lació sector P10</strong><ul><li><a href="/ARXIUS/documents/plan.pdf">Projecte</a></li></ul></div>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['titulo'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fase', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service catalogue</html>', SETTINGS['url'])
