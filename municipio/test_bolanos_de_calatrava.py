"""Offline regression tests for instrument grouping and conservative semantics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.bolanos_de_calatrava import (
    BASE, SOURCE, BolanosDeCalatravaAyuntamientoAdapter, content, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    return '''<article about="/node/2352"><div class="ps_body_pageStatic">
    MODIFICACIONES PUNTUALES <a href="/node/2347">INFORMACIÓN</a></div>
    <div class="ps_adjunto_pageStatic">
    <a href="/sites/default/files/a.pdf">2025-03-07 Anuncio DOCM aprobación definitiva modificación puntual nº 6</a>
    <a href="/sites/default/files/b.pdf">02.- MP_6_POM_Bolaños_2024_06_21_firma.pdf</a>
    <a href="/sites/default/files/c.pdf">2025-01-16 Anuncio aprobación corrección errores nº 1 del POM</a>
    <a href="/sites/default/files/d.pdf">Anuncio BOP aprobación corrección de errores nº 1 del POM</a>
    </div>''' + extra + '</article>'


class ParserTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows, children = parse_inventory(inventory())
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(children, [BASE + '/node/2347'])
        self.assertIn('correccion-1', rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '13023')
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
                self.assertIsNone(row[key])
            self.assertEqual(row['documentos'][0]['source_url'], SOURCE)

    def test_all_documents_and_sections_preserved(self):
        adapter = BolanosDeCalatravaAyuntamientoAdapter('bolanos-de-calatrava')
        pages = {SOURCE: inventory(), BASE + '/node/2347': '''<article about="x">
        <a href="https://drive.google.com/file/d/abc/view?usp=drive_link">Memoria</a>
        <a href="/node/2350">Textos</a></article>''', BASE + '/node/2350': '''<article about="x">
        <a href="/sites/default/files/n.pdf">Normativa</a>
        <a href="/node/2347">Volver</a></article>'''}
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 3)
            self.assertEqual(result['documents'], 6)
            self.assertEqual(len(rows[0]['documentos']), 2)

    def test_pagination_fails(self):
        for extra in ['<nav class="pager">2</nav>', '<a href="?page=1">2</a>', '<a href="x" rel="next">Más</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory(extra))
        # Unrelated calendar outside the article is not an inventory page.
        self.assertIsNotNone(content(inventory() + '<nav class="pager">Calendar</nav>'))

    def test_unknown_attachment_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('02.- MP_6_POM_Bolaños_2024_06_21_firma.pdf', 'Solicitud licencia de obras'))

    def test_no_placeholder(self):
        for html in ['<html>Access denied</html>', '<article about="x">Solicitud licencia</article>']:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('bolanos-de-calatrava')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BolanosDeCalatravaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
