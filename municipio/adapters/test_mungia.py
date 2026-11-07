import unittest
from municipio.adapters.mungia import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_concrete_plan_and_technical_documents(self):
        rows = parse_inventory('<html><head><title>Mungia – Plan Orokorra</title></head><body><a href="/wp-content/uploads/2023/02/01-Aurrerapena.pdf">AURRERAPENA</a><a href="/wp-content/uploads/2021/07/MANUAL.pdf">Manual</a></body></html>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertNotIn(field, rows[0])
    def test_no_documents_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html><head><title>Plan</title></head><body>Contact us</body></html>', SETTINGS['url'])
