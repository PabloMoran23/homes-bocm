"""Offline parser and adapter contract checks; no network needed."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.marchamalo import (
    MarchamaloAyuntamientoAdapter, SOURCE, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def link(label, identifier):
    return f'<a href="https://drive.google.com/file/d/{identifier}/view?usp=sharing">{label}</a>'


FIXTURE = '''<meta property="article:modified_time" content="2024-04-09">
<nav><a href="/licencias/">Solicitud de licencia</a></nav>
<div id="main-content-block">
<p>''' + link('&gt; PGOU – Plan General de Ordenación Urbana', 'general') + '''</p>
<p>''' + link('+ Uso Industrial', 'industrial') + '''</p>
<p>''' + link('+ Modificaciones', 'mods') + '''</p>
<p>&gt; PLANES PARCIALES</p>
<p>''' + link('+ SP.pp.41', 'pp41') + '''</p>
<p>''' + link('+ SP.pp.41', 'pp41-b') + '''</p>
<p>''' + link('+ SP.pp.41', 'pp41') + '''</p>
<p>+ SP.od.51</p>
<p>&gt; PLANES ESPECIALES</p><p>+ PERI</p>
<p>&gt; ESTUDIOS DE DETALLE</p>
<p>''' + link('+ SUE 551', 'sue551') + '''</p>
<p>+ SUE 552</p></div>
<a href="/noticias/">Anuncio de licitación</a>'''


class MarchamaloTests(unittest.TestCase):
    def test_group_documents_and_exclude_navigation_and_unlinked(self):
        rows, unlinked = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2, 1])
        self.assertEqual(unlinked, ['Plan parcial: SP.od.51', 'Plan especial: PERI', 'Estudio de detalle: SUE 552'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '19171')
            self.assertEqual(row['provincia'], 'Guadalajara')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertTrue(all(d['provenance_url'] == SOURCE for d in row['documentos']))

    def test_identity_survives_sharing_query_changes(self):
        a, _ = parse_inventory(FIXTURE)
        b, _ = parse_inventory(FIXTURE.replace('?usp=sharing', '?usp=drive_link'))
        self.assertEqual([r['id'] for r in a], [r['id'] for r in b])

    def test_municipal_drive_folder_variants(self):
        html = FIXTURE.replace('/file/d/general/view?usp=sharing', '/folderview?id=general&amp;usp=sharing')
        html = html.replace('/file/d/mods/view?usp=sharing', '/drive/folders/mods?usp=sharing')
        rows, _ = parse_inventory(html)
        self.assertEqual(rows[0]['documentos'][0]['drive_id'], 'general')
        self.assertEqual(rows[0]['documentos'][0]['tipo'], 'carpeta')
        self.assertEqual(rows[0]['documentos'][2]['tipo'], 'carpeta')

    def test_reject_partial_or_changed_inventory(self):
        variants = [
            '<html>Iniciar sesión</html>',
            FIXTURE.replace('id="main-content-block"', 'id="changed"'),
            FIXTURE.replace('&gt; ESTUDIOS DE DETALLE', '&gt; OTHER'),
            FIXTURE.replace('drive.google.com', 'example.org'),
            FIXTURE.replace('+ SP.pp.41', '+ Solicitud de licencia'),
            FIXTURE.replace('&gt; ESTUDIOS DE DETALLE', 'ESTUDIOS DE DETALLE'),
        ]
        for html in variants:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_never_silently_truncated(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="page-numbers">2</div>',
                      '<a href="?page=2">Siguiente</a>'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Paginated'):
                parse_inventory(FIXTURE.replace('</div>', extra + '</div>'))

    @patch('municipio.adapters.marchamalo.requests.get')
    def test_refresh_and_failures_preserve_previous_snapshot(self, get):
        get.return_value = Mock(text=FIXTURE, url=SOURCE)
        adapter = MarchamaloAyuntamientoAdapter()
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            saved = output.read_text()
            self.assertEqual(len([json.loads(s) for s in saved.splitlines()]), 3)
            get.return_value = Mock(text='<html>Login</html>', url=SOURCE)
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), saved)
            get.return_value = Mock(text=FIXTURE, url='https://example.org/')
            with self.assertRaisesRegex(ValueError, 'redirect'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), saved)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('marchamalo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '19171')
        self.assertEqual(manifest.provincia, 'Guadalajara')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.marchamalo:MarchamaloAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
