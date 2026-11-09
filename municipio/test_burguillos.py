import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.burguillos import (
    BurguillosAyuntamientoAdapter, ENDORSEMENT, PBOM, PGOU, PGOU_DOC_PATH,
    parse_pbom, parse_pgou_page,
)
from municipio.manifest import load_manifest


def pgou_page(number, links=()):
    return ('<h2>Plan General de Ordenación Urbana (PGOU)</h2><table><tr><td>'
            f'<a href="{PGOU_DOC_PATH}{number}.PDF">Plano {number}</a>'
            '</td></tr></table>' + ''.join(
                f'<a href="{PGOU}?pagegalleryfiles-1-2={n}#galleryfiles-1-2">{n}</a>'
                for n in links))


PBOM_HTML = '''<h1>Plan Básico de Ordenación Municipal de Burguillos</h1>
<a href="/wp-content/uploads/2025/09/memoria.pdf">Memoria general</a>
<a href="/wp-content/uploads/2025/09/memoria.pdf">Memoria general</a>
<a href="https://other.es/plan.pdf">Otro municipio</a>
<a href="/wp-content/uploads/2024/04/manual.pdf">Manual de participación</a>'''


class BurguillosTests(unittest.TestCase):
    def test_pgou_scopes_documents_and_follows_fragmentless_pages(self):
        html = pgou_page(1, (1, 2)) + '<a href="https://other.es/unrelated.pdf">Obra</a>'
        docs, pages, _ = parse_pgou_page(html, PGOU)
        self.assertEqual(len(docs), 1)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all('#' not in u for u in pages))
        with self.assertRaises(ValueError):
            parse_pgou_page('<h2>Plan General de Ordenación Urbana (PGOU)</h2>', PGOU)

    def test_pbom_deduplicates_and_excludes_other_municipalities(self):
        docs = parse_pbom(PBOM_HTML)
        self.assertEqual(len(docs), 2)
        self.assertFalse(any('other.es' in d['url'] for d in docs))
        with self.assertRaises(ValueError):
            parse_pbom(PBOM_HTML.replace('Memoria general', 'Formulario de licencia'))
        with self.assertRaises(ValueError):
            parse_pbom(PBOM_HTML + '<a rel="next" href="/page/2">Next</a>')

    def run_inventory(self, directory, repeat=False, endorsed=True):
        adapter = BurguillosAyuntamientoAdapter('burguillos')
        def fetch(session, url):
            if url == PGOU:
                return pgou_page(1, (1, 2))
            if 'pagegalleryfiles' in url:
                n = int(url.rsplit('=', 1)[1])
                return pgou_page(1 if repeat else n, (1, 2, 3) if n == 2 else ())
            if url == ENDORSEMENT:
                return f'<a href="{PBOM}">PBOM</a>' if endorsed else '<p>missing</p>'
            if url == PBOM:
                return PBOM_HTML
            raise AssertionError(url)
        with patch.object(adapter, '_fetch', side_effect=fetch):
            adapter.backfill_proyectos(Path(directory) / 'proyectos.jsonl')
        return [json.loads(line) for line in (Path(directory) / 'proyectos.jsonl').read_text().splitlines()]

    def test_full_walk_groups_documents_and_preserves_semantics(self):
        with tempfile.TemporaryDirectory() as d:
            rows = self.run_inventory(d)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)  # page 3 discovered on page 2
        self.assertEqual(len(rows[1]['documentos']), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41019')
            for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)
            self.assertFalse(row['publication_ready'])

    def test_failed_pagination_or_provenance_does_not_write_partial_output(self):
        for kwargs in ({'repeat': True}, {'endorsed': False}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):
                    self.run_inventory(d, **kwargs)
                self.assertFalse((Path(d) / 'proyectos.jsonl').exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('burguillos')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'licencias.jsonl'
            result = BurguillosAyuntamientoAdapter('burguillos').backfill_licencias(p)
            self.assertTrue(result['disabled'])
            self.assertEqual(p.read_text(), '')


if __name__ == '__main__':
    unittest.main()
