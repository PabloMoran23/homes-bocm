import unittest
from municipio.adapters.chipiona import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_specific_plans_and_exclude_forms(self):
        rows = parse_inventory('<h3 class="package-title"><a href="/download/proyecto-quemados/">Proyecto de urbanización Los Quemados</a></h3><h3 class="package-title"><a href="/download/modelo/">Modelo 03 Licencias de obras</a></h3><h3 class="package-title"><a href="/download/ordenanza/">Ordenanza de licencias</a></h3>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fase', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Generic department contacts</html>', SETTINGS['url'])
