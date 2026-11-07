import unittest
from municipio.adapters.palamos import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_actual_instrument_and_exclude_unrelated(self):
        rows = parse_inventory('<html><head><title>POUM de Palamós</title></head><body><a href="planols/pdf/NORMES/text.pdf">Normativa</a><a href="https://example.org/unrelated.pdf">External</a></body></html>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['titulo'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fase', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service catalogue</html>', SETTINGS['url'])
