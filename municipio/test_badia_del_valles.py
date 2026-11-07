import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.badia_del_valles import (
    BASE, SOURCE, BadiaDelVallesAyuntamientoAdapter, parse_documents, parse_inventory,
)

INVENTORY = '''<meta charset="iso-8859-1"><ul id="categoria_ul_118">
<li><div><a href="fitxes.php?categoria=590">Modificació del Pla General Metropolità</a></div>
<ul><li><div><a href="fitxes.php?categoria=591">Acord</a></div></li>
<li><div><a href="fitxes.php?categoria=592">Normativa</a></div></li></ul></li></ul>'''


def document(name):
    url = 'ARXIUS/Urbanisme/example/' + name + '.pdf'
    return f'''<div class="div_pdf"><a href="{url}"><img></a>
    <p class="descri_pdf">{name}</p><a class="linkpdf" href="{url}">{name}.pdf</a></div>'''


class BadiaParserTests(unittest.TestCase):
    def test_grouping_snapshot_and_semantics(self):
        adapter = BadiaDelVallesAyuntamientoAdapter('badia-del-valles')
        pages = {SOURCE: INVENTORY.encode('iso-8859-1'),
                 BASE + 'fitxes.php?categoria=591': document('Acord'),
                 BASE + 'fitxes.php?categoria=592': document('Normativa')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(path)
            original = path.read_text()
            rows = [json.loads(line) for line in original.splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['titulo'], 'Modificació del Pla General Metropolità')
            self.assertEqual(row['codigo_ine'], '08904')
            self.assertEqual([d['grupo'] for d in row['documentos']], ['Acord', 'Normativa'])
            self.assertEqual(len({d['url'] for d in row['documentos']}), 2)
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            state = Path(tmp) / 'state.json'
            adapter.update_proyectos(path, state)
            self.assertEqual(path.read_text(), original)
            self.assertFalse(state.exists())

    def test_no_navigation_or_licence_form_as_project(self):
        for html in ('<a href="fitxes.php?categoria=590">Planejament</a>',
                     '<form>Sol·licitud llicència obres</form>',
                     INVENTORY.replace('Modificació del Pla General Metropolità', 'Contractació de serveis')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected_in_inventory_and_documents(self):
        for pager in ('<a href="?categoria=591&amp;pagina=2">2</a>',
                      '<a href="more" rel="next">more</a>', '<div class="paginacio"></div>'):
            with self.subTest(pager=pager):
                with self.assertRaises(ValueError):
                    parse_inventory(INVENTORY + pager)
                with self.assertRaises(ValueError):
                    parse_documents(document('Plan') + pager, SOURCE, 'Plan')

    def test_missing_and_foreign_documents_rejected(self):
        for html in ('<p>Login</p>', document('Plan').replace('ARXIUS/Urbanisme/', 'https://foreign.example/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html, SOURCE, 'Plan')

    def test_failure_keeps_previous_snapshot(self):
        adapter = BadiaDelVallesAyuntamientoAdapter('badia-del-valles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[INVENTORY, document('Plan'), '<p>missing</p>']):
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous\n')

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licences.jsonl'
            result = BadiaDelVallesAyuntamientoAdapter('badia-del-valles').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
