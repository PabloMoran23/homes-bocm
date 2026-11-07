import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.capdepera import (
    SOURCE, CapdeperaAyuntamientoAdapter, parse_consolidation, parse_inventory,
)

BOIB_URL = 'https://www.caib.es/eboibfront/ca/2020/11238/637516/acord'
BOIB = '''<p>Núm. 138 - 8 / agost / 2020</p><div class="caja"><p>Acord relatiu al text consolidat de les normes de Capdepera</p>
<a class="document" href="/eboibfront/pdf/ca/2020/138/1065027">PDF</a></div>
<p>La Comissió en sessió de dia 24 d'abril de 2020, ha pres l'acord següent:
Donar conformitat al text consolidat. Aprovades el 14 de març de 1986.</p>'''
ROOT = '''<div id="block-consell-main-content"><div class="links-results">
<div class="flex-wrap"><h4>Text consolidat NNSS Capdepera</h4><a href="%s">Visitar</a></div></div>
<div class="pager"><a rel="next" href="?page=1">Next</a></div></div>''' % BOIB_URL
DETAIL = '''<div id="block-consell-main-content"><article class="link-detail"><div class="prose">
Modificació 2/2013 de les Normes Subsidiàries del Terme Municipal de Capdepera, en relació al vial de comunicació entre la Font de Sa Cala i la Carretera de Ses Coves
</div></article></div>'''


class CapdeperaTests(unittest.TestCase):
    def test_dates_and_document_grouping(self):
        row = parse_consolidation(BOIB, BOIB_URL)
        self.assertEqual(row['fecha_acuerdo'], '2020-04-24')
        self.assertEqual(row['fecha_publicacion'], '2020-08-08')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['lat'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertNotIn('definitiva', row['fase'])

    def test_missing_dates_not_inferred(self):
        row = parse_consolidation(BOIB.replace("24 d'abril de 2020", 'data desconeguda').replace('8 / agost / 2020', 'data desconeguda'), BOIB_URL)
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_forms_empty_folders_and_news_are_not_records(self):
        html = '<div id="block-consell-main-content"><h3>Normes Subsidiàries</h3><a href="/form.pdf">Sol·licitud llicència Urbanística</a><p>Notícies i contractació</p></div>'
        self.assertEqual(parse_inventory(html, SOURCE), ([], [], []))
        with self.assertRaises(ValueError):
            parse_inventory('<html>Login</html>', SOURCE)
        with self.assertRaises(ValueError):
            parse_consolidation('<html>BOIB Capdepera</html>', BOIB_URL)

    def test_named_modification_is_one_instrument(self):
        rows = parse_inventory(DETAIL, SOURCE + '/detail')[2]
        self.assertEqual(len(rows), 1)
        self.assertIn('2/2013', rows[0]['titulo'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fase'])

    def test_complete_pagination_and_stable_snapshot(self):
        adapter = CapdeperaAyuntamientoAdapter('capdepera')
        pages = {SOURCE: ROOT, SOURCE + '?page=1': DETAIL, BOIB_URL: BOIB}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            first = output.read_text()
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 3)
            adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(first, output.read_text())
            rows = [json.loads(line) for line in first.splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_failure_does_not_replace_snapshot(self):
        adapter = CapdeperaAyuntamientoAdapter('capdepera')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value='<html>Login</html>'):
            output = Path(tmp) / 'out.jsonl'
            output.write_text('prior snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'prior snapshot')


if __name__ == '__main__':
    unittest.main()
