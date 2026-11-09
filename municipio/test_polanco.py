"""Offline parser and traversal regression tests for Polanco."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.polanco import HOME, CATALOGUE, PolancoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def detail(title, body):
    return f'<main><h1 class="entry-title">{title}</h1><div class="entry-content">{body}</div></main>'


def inventory(*slugs):
    children = ''.join(f'<li><a href="{CATALOGUE}{slug}/">{slug}</a></li>' for slug in slugs)
    return f'<ul><li><a href="{CATALOGUE}">Planeamiento</a><ul>{children}</ul></li></ul>'


class PolancoTests(unittest.TestCase):
    def test_inventory_discovers_all_children_and_deduplicates(self):
        html = inventory('plan-general', 'modificacion-1', 'estudio-1')
        links = Adapter.parse_inventory(html + html + '<a href="/noticias/">Otra noticia</a>')
        self.assertEqual(len(links), 3)
        self.assertIn(CATALOGUE + 'estudio-1/', links)

    def test_no_placeholder_and_no_silent_pagination(self):
        for html in ('<html>Login</html>', inventory('a') + '<a rel="next" href="/page/2">2</a>',
                     inventory('a') + '<div class="page-links">1 2</div>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Plan General', ''), CATALOGUE + 'plan/')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Plan General', '<a href="/page/2/">Siguiente</a>'), CATALOGUE + 'plan/')

    def test_documents_grouped_and_dates_are_not_agreement_dates(self):
        html = detail('Modificación puntual Nº 1', '''
          <h2>Informe Ambiental Estratégico</h2><a href="/ambiental.pdf">BOC de 8 de mayo de 2017</a>
          <h2>Aprobación Definitiva</h2>
          <a href="http://www.aytopolanco.org/uno con espacio.pdf">BOC de 1 de febrero de 2018</a>
          <a href="/dos.pdf">BOC de 1 de febrero de 2018</a>
          <a href="/dos.pdf">Duplicado</a>
          <a href="/errata.pdf">BOC de 13 de marzo de 2018. Corrección de errores</a>''')
        row = Adapter.parse_detail(html, CATALOGUE + 'modificacion-1/')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['fecha_publicacion'], '2018-02-01')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha'])
        self.assertIn('%20', row['documentos'][1]['url'])
        self.assertEqual(row['documentos'][0]['fecha_publicacion'], '2017-05-08')

    def test_missing_dates_and_geometry_not_inferred_from_filename(self):
        row = Adapter.parse_detail(detail('Estudio de detalle AAM4',
            '<a href="/20231226_anuncio.pdf">Estudio de detalle AAM4</a>'), CATALOGUE + 'aam4/')
        for key in ('fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_conflicting_sector_is_excluded(self):
        row = Adapter.parse_detail(detail('Plan Parcial URB-10',
            '<a href="/P.-COMPENSACIÓN-URB-8.pdf">PROYECTO DE COMPENSACIÓN URB10</a>'), CATALOGUE + 'urb10/')
        self.assertIsNone(row)

    def test_traversal_and_failure_preserves_existing_output(self):
        adapter = Adapter('polanco')
        pages = {HOME: inventory('uno', 'dos'),
                 CATALOGUE + 'uno/': detail('Plan General', '<a href="/plan.pdf">Memoria</a>'),
                 CATALOGUE + 'dos/': detail('Estudio de detalle UA P1', '<a href="/p1.pdf">Estudio</a>')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda session, url: pages[url]), patch('municipio.adapters.polanco.time.sleep'):
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 2)
            before = path.read_text()
            self.assertEqual(len({json.loads(line)['id'] for line in before.splitlines()}), 2)
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), before)
            pages[CATALOGUE + 'dos/'] = '<html>Error</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('polanco')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            adapter.backfill_licencias(path)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
