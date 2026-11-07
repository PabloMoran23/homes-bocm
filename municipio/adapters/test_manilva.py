import unittest
from municipio.adapters.manilva import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_concrete_plan_and_technical_documents(self):
        rows = parse_inventory('<div id="elementor-tab-content-1835"><h4>Plan General 1994</h4><a href="/archivos/PGOU1994/norma.pdf">Normas</a><h4>Adaptación parcial LOUA</h4><a href="/archivos/PLANOS/plano.pdf">Plano</a><a href="/wp-content/uploads/form.pdf">Formulario</a></div>', SETTINGS['url'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertNotIn(field, rows[0])
    def test_no_documents_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html><head><title>Plan</title></head><body>Contact us</body></html>', SETTINGS['url'])
