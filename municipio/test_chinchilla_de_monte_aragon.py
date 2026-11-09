import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.chinchilla_de_monte_aragon import (
    SOURCE, ChinchillaDeMonteAragonAyuntamientoAdapter, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    return ('<div id="content_area"><h1>PLAN DE ORDENACIÓN MUNICIPAL</h1>'
            '<a class="diyfeLinkAsButton" href="/urbanismo/memoria/">Memoria</a>'
            '<a class="diyfeLinkAsButton" href="/urbanismo/planos/">Planos</a>'
            + extra + '<h1>URBANIZACIÓN AR5</h1>'
            '<a class="diyfeLinkAsButton" href="/urbanismo/ar5/">AR5</a></div>')


def section(title, extra=''):
    return ('<div id="content_area"><h1>' + title + '</h1>'
            '<a href="/app/download/123/Memoria+de+ordenaci%C3%B3n.pdf">imagen</a>'
            '<a href="/app/download/123/Memoria+de+ordenaci%C3%B3n.pdf">truncado[...]</a>'
            + extra + '</div>')


class ParserTests(unittest.TestCase):
    def test_discovery_and_document_identity(self):
        sections = parse_inventory(inventory())
        self.assertEqual(len(sections), 2)
        self.assertFalse(any('ar5' in url for url in sections))
        docs = parse_documents(section('Memoria'), SOURCE + 'memoria/', 'Memoria')
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['titulo'], 'Memoria de ordenación.pdf')
        self.assertEqual(docs[0]['id_origen'], '123')

    def test_fail_closed_on_changed_or_paginated_sources(self):
        for html in ('<div></div>', '<div id="content_area"><h1>Error</h1></div>',
                     inventory('<a rel="next" href="?p=2">2</a>'),
                     inventory('<a href="?page=2">2</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        for html in (section('Wrong'), '<div id="content_area"><h1>Memoria</h1></div>',
                     section('Memoria', '<a href="https://other.invalid/app/download/2/x.pdf">x</a>'),
                     section('Memoria', '<a href="?page=2">Siguiente</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html, SOURCE + 'memoria/', 'Memoria')

    def test_grouping_null_dates_and_snapshot(self):
        adapter = ChinchillaDeMonteAragonAyuntamientoAdapter('chinchilla-de-monte-aragon')
        pages = {SOURCE: inventory(), SOURCE+'memoria/': section('Memoria'),
                 SOURCE+'planos/': section('Planos')}
        with tempfile.TemporaryDirectory() as folder:
            output, state = Path(folder)/'proyectos.jsonl', Path(folder)/'state.json'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['rows'], 1)
            row = json.loads(output.read_text())
            self.assertEqual(len(row['documentos']), 1)
            self.assertEqual(len(row['documentos'][0]['procedencia']), 2)
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertIsNone(row[key])
            self.assertFalse(state.exists())
            previous = output.read_bytes()
            pages[SOURCE+'planos/'] = '<html>Error</html>'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(previous, output.read_bytes())
            adapter.backfill_licencias(Path(folder)/'licencias.jsonl')
            self.assertEqual((Path(folder)/'licencias.jsonl').read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('chinchilla-de-monte-aragon')
        self.assertIsInstance(load_portal_adapter(manifest), ChinchillaDeMonteAragonAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Albacete')


if __name__ == '__main__':
    unittest.main()
