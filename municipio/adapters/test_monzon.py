import unittest
from municipio.adapters.monzon import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_actual_instrument_and_exclude_unrelated(self):
        rows = parse_inventory('<main><a href="/documents/5482479/plan-rio?download=true">Plan director del río Sosa..pdf</a><a href="/documents/5482479/accion?download=true">Plan de Acción 2022.pdf</a></main>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['titulo'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fase', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service catalogue</html>', SETTINGS['url'])
