import unittest
from municipio.adapters.caldes_de_montbui import parse_inventory, SETTINGS

class InventoryTest(unittest.TestCase):
    def test_actual_instrument_and_exclude_unrelated(self):
        rows = parse_inventory('<table><thead><tr><th>Número expedient</th><th>Tema</th><th>Enllaç</th><th>Documents</th></tr></thead><tbody><tr><td>2003/007926/B</td><td>POUM Caldes de Montbui</td><td><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/207531/documents">RPUC</a></td><td><a href="/documents/29428/POUM">POUM</a></td></tr></tbody></table>', SETTINGS['url'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['titulo'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ('fecha', 'fase', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertNotIn(field, rows[0])
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service catalogue</html>', SETTINGS['url'])
