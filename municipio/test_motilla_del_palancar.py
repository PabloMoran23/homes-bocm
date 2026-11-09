"""Parser and snapshot safety checks; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.motilla_del_palancar import (
    SOURCE, MotillaDelPalancarAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def entry(identity='637', title='01.-1994-04-07 NORMAS SUBSIDIARIAS', docs=('memoria.pdf', 'plano.pdf')):
    links = ''.join(f'<a class="post__attachment-link" href="/wp-content/uploads/{doc}">{doc}</a>' for doc in docs)
    return (f'<article class="lsvr_document post-{identity}"><h2><a class="post__title-link" '
            f'href="/documentos/plan-{identity}/">{title}</a></h2>{links}</article>')


class MotillaTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows, pages, skipped = parse_inventory(entry() + entry())
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '16134')
        self.assertEqual(rows[0]['provincia'], 'Cuenca')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon', 'fase'):
            self.assertIsNone(rows[0][key])
        self.assertIn('1994-04-07', rows[0]['fecha_texto_origen'])
        self.assertEqual(rows[0]['documentos'][0]['source_url'], rows[0]['url'])
        self.assertEqual((pages, skipped), ([], []))

    def test_instrument_types(self):
        titles = [('PAU SAU 3-1', 'programa_actuacion_urbanizadora'),
                  ('ED LAS LOMAS Z-9', 'estudio_detalle'),
                  ('MODPUNT3-SAU3', 'modificacion_planeamiento'),
                  ('PLAN PARCIAL ZONA 1-16', 'plan_parcial'),
                  ('URBANA CAMP DEL TURIA', 'plan_especial_reforma_interior')]
        for title, kind in titles:
            with self.subTest(title=title):
                rows, _, _ = parse_inventory(entry(title=title, docs=('Portada_PERI.pdf',)))
                self.assertEqual(rows[0]['tipo'], kind)

    def test_forms_and_procurement_excluded(self):
        for title in ('SOLICITUD DE LICENCIA', 'LICITACIÓN OBRAS'):
            rows, _, skipped = parse_inventory(entry(title=title))
            self.assertFalse(rows)
            self.assertEqual(len(skipped), 1)

    def test_changed_source_fails(self):
        for html in ('<html>Access denied</html>', entry(docs=()),
                     entry(title='ORDENANZA DE TASAS'),
                     entry().replace('/wp-content/uploads/', 'https://example.org/'),
                     entry() + entry(title='PAU SAU 3-1')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_and_cycle(self):
        second = SOURCE + 'page/2/'
        pages = {SOURCE: entry() + f'<a rel="next" href="{second}">Siguiente</a>',
                 second: entry('663', 'PP CUEVAS FRIAS SAU-1') + f'<a href="{second}">2</a>'}
        adapter = MotillaDelPalancarAyuntamientoAdapter('motilla-del-palancar')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda u: pages[u]) as fetch:
                report = adapter.backfill_proyectos(out)
            self.assertEqual(report['rows'], 2)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)
            self.assertEqual(report['source_urls'], [SOURCE, second])
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=ValueError('source failure')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
        with self.assertRaises(ValueError):
            parse_inventory(entry() + '<a rel="next" href="https://example.org/page/2/">Next</a>')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('motilla-del-palancar')
        self.assertEqual(manifest.provincia, 'Cuenca')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MotillaDelPalancarAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
