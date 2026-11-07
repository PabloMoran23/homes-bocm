import unittest
from municipio.adapters.lora_del_rio import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_concrete_plan_and_technical_documents(self):
        rows = parse_inventory('<html><head><title>PGOM Lora del Río</title></head><body><a href="/wp-content/uploads/2025/10/diagnostico.pdf">Diagnóstico previo</a><a href="/wp-content/uploads/2024/10/manual.pdf">Manual de participación</a><a href="https://example.org/diagnostico.pdf">Diagnóstico otro municipio</a></body></html>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertNotIn(field, rows[0])
    def test_no_documents_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html><head><title>Plan</title></head><body>Contact us</body></html>', SETTINGS['url'])
