import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cabrera_de_mar import CabreraDeMarAyuntamientoAdapter, SOURCE, parse_page


def page(title, body='', extra=''):
    return '<div id="readspeakerPage"><h1>' + title + '</h1>' + body + '</div>' + extra


def instrument():
    return page('Modificació puntual del POUM Can Serra',
                '<span class="updated">Darrera actualització: 20.02.2025 | 12:23</span>',
                '<section id="page-documents"><a href="/media/repository/one.pdf">Part 1</a>'
                '<a href="/media/repository/two.pdf">Part 2</a>'
                '<a href="/media/repository/one.pdf">Part 1 repeated</a></section>')


class CabreraTests(unittest.TestCase):
    def test_group_documents_and_distinguish_dates(self):
        children, row = parse_page(instrument(), SOURCE + '/modificacio')
        self.assertEqual(children, [])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_actualizacion_pagina'], '2025-02-20')
        for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])

    def test_reject_navigation_forms_and_empty_categories(self):
        for html in ('<h1>Login</h1>', page('Sol·licitud de llicència'), page('POUM')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    def test_pagination_never_silently_truncated(self):
        for extra in ('<div class="pagination">2</div>', '<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Següent</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_page(page('POUM', extra), SOURCE)

    def test_complete_tree_deduplicates_responsive_links(self):
        index = page('Planejament Vigent', '<ul class="widgetMenu">'
                     '<a href="' + SOURCE + '/can-serra">Can Serra</a>'
                     '<a href="' + SOURCE + '/can-serra">Can Serra</a>'
                     '<a href="' + SOURCE + '/second">Second</a></ul>')
        adapter = CabreraDeMarAyuntamientoAdapter('cabrera-de-mar')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda u: index if u == SOURCE else instrument()) as fetch:
            out = Path(tmp) / 'projects.jsonl'
            report = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(report['rows'], 2)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(len({r['id'] for r in map(json.loads, out.read_text().splitlines())}), 2)

    def test_failure_preserves_previous_snapshot(self):
        adapter = CabreraDeMarAyuntamientoAdapter('cabrera-de-mar')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=page('POUM')):
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous')


if __name__ == '__main__':
    unittest.main()
