import unittest
from municipio.adapters.monforte_de_lemos import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_specific_plan_documents_and_semantics(self):
        rows = parse_inventory('<article><div class="field-name-body"><h2>Plan Especial do Casco Histórico</h2><a href="/pdf/articulos_urbanismo_obras/document.pdf">Normativa</a><a href="https://example.org/foreign.pdf">Foreign</a></div></article>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>generic homepage</html>', SETTINGS['url'])
    def test_empty_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<article><div class="field-name-body"><h2>Plan Especial do Casco Histórico</h2><a href="https://example.org/foreign.pdf">Foreign</a></div></article>', SETTINGS['url'])
