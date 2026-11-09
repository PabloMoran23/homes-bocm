"""Offline contract tests for the public PGM inventory."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.oliva_de_la_frontera import (
    SOURCE, OlivaDeLaFronteraAdapter, parse_page,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

LABEL = ('PLAN GENERAL MUNICIPAL OLIVA DE LA FRONTERA (versión aprobada inicialmente '
         'por el pleno en sesión ordinaria celebrada el día 31-7-18)')
DOC = 'https://olivafrontera.com/wp-content/uploads/2018/07/memoria.pdf'
CHILD = SOURCE + 'tomo-i-informacion/'


def page(body, nav=''):
    return f'<main><section id="content"><div class="post-content">{body}</div></section><aside>{nav}</aside></main>'


class InventoryTests(unittest.TestCase):
    def test_content_scope_and_public_navigation(self):
        html = '<header><a href="/wp-content/uploads/licencia.pdf">Formulario</a></header>'
        html += page(f'<a href="{DOC}">Memoria</a>', f'<a href="{CHILD}">Tomo I</a>')
        pages, docs, _ = parse_page(html, SOURCE)
        self.assertEqual(pages, [CHILD])
        self.assertEqual(docs, [{'titulo': 'Memoria', 'url': DOC, 'source_page': SOURCE}])

    def test_grouping_dates_provenance_and_full_refresh(self):
        fixtures = {
            SOURCE: page(f'<a href="{DOC}">Memoria</a>', f'{LABEL}<a href="{CHILD}">Tomo I</a>'),
            CHILD: page(f'<a href="{DOC}#page=1">Memoria</a><a href="/wp-content/uploads/plano.pdf">Plano</a>', f'<a href="{SOURCE}">Volver</a>'),
        }
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            adapter = OlivaDeLaFronteraAdapter('oliva-de-la-frontera')
            with patch.object(adapter, '_fetch', side_effect=lambda session, url: fixtures[url]) as fetch:
                result = adapter.backfill_proyectos(out)
                self.assertEqual(fetch.call_count, 2)
                first = out.read_text()
                adapter.update_proyectos(out, Path(folder) / 'state.json')
                self.assertEqual(out.read_text(), first)
            rows = [json.loads(line) for line in first.splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['fecha_acuerdo'], '2018-07-31')
            self.assertEqual(row['fase'], 'aprobacion_inicial')
            self.assertEqual(result['documents'], 2)
            self.assertEqual(next(d for d in row['documentos'] if d['url'] == DOC)['source_pages'], [SOURCE, CHILD])
            for field in ['fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertNotIn(field, row)

    def test_pagination_and_unreviewed_links_fail(self):
        for body in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Siguiente</a>',
                     '<a href="https://other.example/project.pdf">Doc</a>',
                     '<a href="/new-inventory/">New inventory</a>']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_page(page(body), SOURCE)

    def test_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            out.write_text('previous\n')
            adapter = OlivaDeLaFronteraAdapter('oliva-de-la-frontera')
            with patch.object(adapter, '_fetch', return_value=page(LABEL)):
                with self.assertRaisesRegex(ValueError, 'No PGM documents'):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')
            with patch.object(adapter, '_fetch', return_value=page(f'<a href="{DOC}">Doc</a>')):
                with self.assertRaisesRegex(ValueError, 'label changed'):
                    adapter.backfill_proyectos(out)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('oliva-de-la-frontera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '06093')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, OlivaDeLaFronteraAdapter)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
