import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.lezo import LezoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, body='', children=()):
    cards = ''.join(f'<a href="{url}"><div class="azpiorri">{label}</div></a>' for url, label in children)
    return f'<div class="region-content"><h1 class="page-header">{title}</h1>{cards}<article class="book"><div class="field--name-body">{body}</div></article></div>'


class LezoTests(unittest.TestCase):
    def test_grouping_recursive_documents_and_dates(self):
        pages = {
            Adapter.SOURCE: page('Plan General de Urbanismo', children=[('/es/bog', 'Plan General de Urbanismo de Lezo publicado'), ('/es/memoria', 'Memoria'), ('/es/planos', 'Planos'), ('/es/mod', 'Segunda modificación puntual del Plan General. AOU 31 Sagasti.')]),
            Adapter.BASE + '/es/bog': page('BOG', 'Plan publicado en el <a href="https://bog.example/2011">Boletín Oficial de Gipuzkoa</a>, el 23 de diciembre de 2011'),
            Adapter.BASE + '/es/memoria': page('Memoria', '<a href="http://www.lezo.net/legacy.pdf">Tomo I</a>'),
            Adapter.BASE + '/es/planos': page('Planos', children=[('/es/hoja', 'Hoja')]),
            Adapter.BASE + '/es/hoja': page('Hoja', '<a href="/map.pdf">Plano</a><a href="/map.pdf">Duplicado</a>'),
            Adapter.BASE + '/es/mod': page('Sagasti', '<a href="/doc.pdf">Documento</a><a href="/anuncio.pdf">Anuncio</a>'),
        }
        adapter = Adapter('lezo')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'out.jsonl'
            adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[0]['documentos']), 3)
            self.assertEqual(rows[0]['fecha_publicacion'], '2011-12-23')
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[1]['fecha_publicacion'])
            self.assertEqual(len(rows[1]['documentos']), 2)
            self.assertTrue(all(row['geometry'] is None for row in rows))
            # A failed refresh must not replace the prior successful snapshot.
            previous = out.read_bytes()
            pages[Adapter.BASE + '/es/hoja'] = page('Hoja')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)

    def test_reject_pagination_and_invalid_content(self):
        for html in [page('Planos') + '<a rel="next" href="?page=1">Next</a>', page('Planos') + '<ul class="pager"><li><a href="/p2">2</a></li></ul>', '<h1>Login</h1>']:
            with self.assertRaises(ValueError):
                Adapter.parse_page(html, Adapter.SOURCE)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('lezo')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
