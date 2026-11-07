import unittest
from municipio.adapters.cabra import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_specific_plans_and_exclude_forms(self):
        rows = parse_inventory('<main id="content"><h1 class="entry-title">Plan General de Ordenación Urbanística</h1><a href="/wp-content/uploads/2023/normas.pdf">Normas</a><a href="https://example.org/form.pdf">Externo</a></main>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fase', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Generic department contacts</html>', SETTINGS['url'])
