"""Offline parser and adapter contract tests; fixtures do not depend on live web."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.catral import (
    INVENTORY, MUNICIPAL_SOURCE, CatralAyuntamientoAdapter,
    collect_projects, parse_directory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def index(*links):
    return ('<h1 id="indextitle">Index of /03055 CATRAL/</h1>'
            '<table id="indexlist">' + ''.join(
                f'<tr><td class="indexcolname"><a href="{href}">{label}</a></td></tr>'
                for href, label in links) + '</table>')


class CatralTests(unittest.TestCase):
    def tree(self):
        category = INVENTORY + '1%20P.%20GENERAL/'
        first = category + '03055-1001%20PGMOD/'
        second = category + '03055-1100%20PGMOD/'
        return {
            INVENTORY: index(('1%20P.%20GENERAL/', '1 P. GENERAL/')),
            category: index(('03055-1001%20PGMOD/', '03055-1001 PGMOD/'),
                            ('03055-1100%20PGMOD/', '03055-1100 PGMOD/')),
            first: index(('1%20APROBACI%d3N/', '1 APROBACIÓN/'),
                         ('registro.pdf', 'Inscripción registro.pdf')),
            first + '1%20APROBACI%d3N/': index(('BOP.pdf', 'Publicación BOP.pdf'),
                                                          ('CTU.pdf', 'Acuerdo CTU.pdf')),
            second: index(('memoria.pdf', 'Memoria.pdf')),
        }

    def test_groups_all_documents_and_preserves_provenance(self):
        tree = self.tree()
        rows, pages = collect_projects(tree.__getitem__)
        self.assertEqual(len(pages), len(tree))
        self.assertEqual([len(r['documentos']) for r in rows], [3, 1])
        self.assertEqual(rows[0]['registro_autonomico_id'], '03055-1001')
        bop = next(d for d in rows[0]['documentos'] if d['titulo'].startswith('Publicación'))
        self.assertIn('1%20APROBACI%d3N/BOP.pdf', bop['url'])
        self.assertEqual(bop['seccion'], '1 APROBACIÓN')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '03055')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['geometry'])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])
        self.assertEqual(rows, collect_projects(tree.__getitem__)[0])

    def test_rejects_empty_changed_and_unidentified_sources(self):
        for html in ['<html>Access denied</html>', index(),
                     index(('licencia.pdf', 'Solicitud licencia.pdf'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                collect_projects(lambda _: html)

    def test_rejects_external_other_municipality_and_parent_entries(self):
        for href in ['https://example.org/x.pdf', '../other.pdf',
                     INVENTORY.replace('03055', '03056') + 'x.pdf', '%2e%2e/x.pdf']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_directory(index((href, 'Document')), INVENTORY)

    def test_pagination_is_never_silently_ignored(self):
        with self.assertRaises(ValueError):
            parse_directory(index(('?page=2', 'Next')), INVENTORY)
        html = '<a href="?C=N;O=D">Sort</a>' + index(('a.pdf', 'A.pdf'))
        self.assertEqual(len(parse_directory(html, INVENTORY)), 1)

    def test_legacy_and_utf8_labels_keep_encoded_urls(self):
        from unittest.mock import Mock
        adapter = CatralAyuntamientoAdapter('catral')
        html = index(('1%20APROBACI%d3N/', '1 APROBACIÓN/'))
        for encoding in ('utf-8', 'iso-8859-1'):
            response = Mock(url=INVENTORY, content=html.encode(encoding))
            with patch('municipio.adapters.catral.requests.get', return_value=response):
                entries = parse_directory(adapter._fetch(INVENTORY), INVENTORY)
            self.assertEqual(entries[0]['titulo'], '1 APROBACIÓN')
            self.assertTrue(entries[0]['url'].endswith('1%20APROBACI%d3N/'))

    def test_failed_traversal_does_not_overwrite_output(self):
        tree = self.tree()
        del tree[next(u for u in tree if u.endswith('1%20APROBACI%d3N/'))]
        adapter = CatralAyuntamientoAdapter('catral')
        municipal = f'<div class="entry-content"><a href="{INVENTORY}">Planeamiento</a></div>'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=lambda u: municipal if u == MUNICIPAL_SOURCE else tree[u]):
                with self.assertRaises(KeyError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_registry_snapshot_and_disabled_licences(self):
        manifest = load_manifest('catral')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '03055')
        self.assertEqual(manifest.provincia, 'Alicante')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        tree = self.tree()
        municipal = f'<div class="entry-content"><a href="{INVENTORY}">Planeamiento</a></div>'
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            state = Path(tmp) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=lambda u: municipal if u == MUNICIPAL_SOURCE else tree[u]):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(s) for s in output.read_text().splitlines()]), 2)
            self.assertFalse(state.exists())
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
