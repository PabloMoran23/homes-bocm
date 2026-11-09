import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.salines_ses import (
    INVENTORY, SOURCE, SalinesSesAyuntamientoAdapter, group_documents, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def card(title, filename, date='13/11/2025'):
    return f'<div><h3>{title}</h3><span>PDF · {date}</span><a download href="/sites/cilma_ses_salines/files/{filename}.pdf">Descarregar</a></div>'


def page(cards, extra=''):
    return '<main><h1>00 NORMES SUBSIDIÀRIES DE PLANEJAMENT</h1>' + cards + extra + '</main>'


CARDS = (card('Text Refós de les Normes Complementàries i Subsidiàries', 'cat')
         + card('Texto Refundido de las Normas Complementarias y Subsidiarias', 'es')
         + card('2-1 2020 Urbà Ses Salines', 'map', '03/08/2021')
         + card("Pla especial de reforma interior d’es Camp Lladó - juliol 2021", 'peri', '03/10/2025'))


class SalinesSesTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = group_documents(parse_inventory(page(CARDS)))
        self.assertEqual([len(r['documentos']) for r in rows], [3, 1])
        self.assertEqual(rows[1]['documentos'][0]['fecha_publicacion'], '2025-10-03')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '07059')
            for key in ('fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertIsNone(row[key])
        self.assertIn('juliol 2021', rows[1]['titulo'])
        self.assertEqual(len({d['url'] for r in rows for d in r['documentos']}), 4)
        self.assertEqual(group_documents(parse_inventory(page(CARDS + CARDS))), rows)

    def test_invalid_and_unrelated_sources(self):
        cases = [page(''), '<main><h1>Sol·licitud de llicència</h1></main>',
                 page(card('Sol·licitud llicència urbanística', 'form')),
                 page(CARDS).replace('/sites/cilma_ses_salines/files/cat.pdf', 'https://example.org/cat.pdf'),
                 page(CARDS).replace('13/11/2025', '31/02/2025'),
                 page(CARDS, '<nav class="pager"><a href="?page=1">Next</a></nav>')]
        for html in cases:
            with self.subTest(html=html[:100]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_snapshot_and_count_guard(self):
        adapter = SalinesSesAyuntamientoAdapter('salines-ses')
        root = f'<main><a href="{SOURCE}">00 NORMES SUBSIDIÀRIES 4 documents</a></main>'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[root, page(CARDS)]):
                report = adapter.update_proyectos(output, Path(temp) / 'state.json')
            self.assertEqual(report['rows'], 2)
            self.assertEqual(len(output.read_text().splitlines()), 2)
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[root.replace('4 documents', '5 documents'), page(CARDS)]):
                with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            self.assertFalse((Path(temp) / 'state.json').exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('salines-ses')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
