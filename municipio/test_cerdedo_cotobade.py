"""Offline parser and failure-safety tests; no downloaded fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cerdedo_cotobade import (
    BASE, SOURCE, CerdedoCotobadeAyuntamientoAdapter, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def html(body):
    return '<main><article><div class="entry-content">' + body + '</div></article></main>'


class ParserTests(unittest.TestCase):
    def test_discovery_excludes_forms_news_and_strategic_plans(self):
        link = '<a href="/servizos/urbanismo/pxom-cerdedo/">PXOM</a>'
        pages = parse_inventory(html(link + link + '''
          <a href="/servizos/urbanismo/pmus-plan-de-mobilidade/">PMUS</a>
          <a href="/news/obra/">Obras</a>
          <a href="/wp-content/uploads/licencia.pdf">Licencia obra maior</a>
          <a href="https://other.example/servizos/urbanismo/fake/">PXOM</a>'''))
        self.assertEqual(pages, [{'url': SOURCE + 'pxom-cerdedo/', 'titulo': 'PXOM'}])

    def test_grouping_provenance_no_inferred_dates_and_no_stray_drive(self):
        page = {'url': SOURCE + 'normas-subsidiarias-cotobade/', 'titulo': 'Normas subsidiarias Cotobade'}
        rows = parse_instrument(html('''
          <a href="/normas.pdf">Normas Subsidiarias I</a>
          <a href="/normas.pdf">Normas Subsidiarias I</a>
          <a href="/2024/Mod-I.pdf">Modificación I</a>
          <a href="/20220726.pdf">Modificación III</a>
          <a href="/20240708.pdf">Corrección de erros</a>
          <a href="/NS2.1.jpg">NS2.1</a>
          <a href="https://drive.google.com/file/d/unrelated/view"><br></a>
          <a href="#accordion">Normativa</a>'''), page)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 2])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['geometry'])
            for doc in row['documentos']:
                self.assertEqual(doc['pagina_fuente'], page['url'])
                self.assertTrue(doc['url'].startswith(BASE))

    def test_rejects_pagination_empty_changed_markup_and_orphan_correction(self):
        for bad in ['<html>Maintenance</html>', html(''),
                    html('<a rel="next" href="/page/2">2</a>'),
                    html('<a href="/page/2">Seguinte</a>')]:
            with self.assertRaises(ValueError):
                parse_inventory(bad)
        page = {'url': SOURCE + 'normas-subsidiarias-cotobade/', 'titulo': 'NNSS'}
        for bad in [html('<a href="#tab">Normativa</a>'),
                    html('<a href="/correction.pdf">Corrección de erros</a>')]:
            with self.assertRaises(ValueError):
                parse_instrument(bad, page)

    def test_failed_refresh_preserves_output(self):
        adapter = CerdedoCotobadeAyuntamientoAdapter('cerdedo-cotobade')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            out.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[
                html('<a href="/servizos/urbanismo/pxom-cerdedo/">PXOM</a>'), html('')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_manifest_loader_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('cerdedo-cotobade'))
        self.assertIsInstance(adapter, CerdedoCotobadeAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
