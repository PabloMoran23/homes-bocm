import unittest
from municipio.adapters.tolosa import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_specific_plans_and_exclude_forms(self):
        rows = parse_inventory('<div class="field-name-body"><p>2-MODIFICACIONES PGOU</p><p class="rteindent1">2.1- MODIFICACIÓN SAN ESTEBAN</p><ul><li><a href="/sites/default/files/avance.pdf">Avance</a></li></ul><p class="rteindent1">2.2-MODIFICACIÓN IURRE</p><ul><li><a href="/sites/default/files/iurre.pdf">Normas</a></li></ul></div>', SETTINGS['url'])
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fase', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Generic department contacts</html>', SETTINGS['url'])
    def test_documents_do_not_leak_between_sections(self):
        rows = parse_inventory('<div class="field-name-body"><p>2-MODIFICACIONES PGOU</p><p class="rteindent1">2.1- MODIFICACIÓN SAN ESTEBAN</p><ul><li><a href="/sites/default/files/avance.pdf">Avance</a></li></ul><p class="rteindent1">2.2-MODIFICACIÓN IURRE</p><ul><li><a href="/sites/default/files/iurre.pdf">Normas</a></li></ul></div>', SETTINGS['url'])
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertTrue(rows[0]['documentos'][0]['url'].endswith('avance.pdf'))
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('iurre.pdf'))
