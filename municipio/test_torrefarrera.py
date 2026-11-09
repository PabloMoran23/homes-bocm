import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.torrefarrera import (
    BASE, PLANNING, PUBLIC, TorrefarreraAyuntamientoAdapter, entries, project_kind,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def listing(items):
    return '<div id="content-core"><table class="listing">' + ''.join(
        f'<tr><td><a class="url contenttype-{kind}" href="{url}"><img></a>'
        f'<a class="url contenttype-{kind}" href="{url}">{title}</a></td></tr>'
        for kind, url, title in items) + '</table></div>'


class TorrefarreraTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = load_manifest('torrefarrera')
        self.assertEqual(manifest.provincia, 'Lleida')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), TorrefarreraAyuntamientoAdapter)

    def test_excludes_applications_procurement_and_unrelated_content(self):
        for title in ('Informació pública llicència d’activitat Bar musical',
                      'Licitació de les obres', 'Projecte activitat de Lloguer de maquinaria industrial',
                      'Formulari llicència d’obres', 'Activitats culturals subvencionades'):
            self.assertIsNone(project_kind(title))

    def test_listing_deduplicates_icons_and_resolves_links(self):
        result = entries(listing([('file', '/doc/view', 'Document')]), PUBLIC)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['url'], BASE + '/doc/view')

    def test_rejects_pagination_in_inventory_and_folder(self):
        for marker in ('<div class="listingBar"><a href="?b_start:int=20">2</a></div>',
                       '<a rel="next" href="?start=20">Next</a>',
                       '<a href="?b_start=20">2</a>'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, 'Pagination'):
                entries('<div id="content-core">' + marker + '</div>', PUBLIC)

    def test_rejects_error_empty_and_external_sources(self):
        for html in ('<h1>Login</h1>', '<div id="content-core"></div>',
                     listing([('file', 'https://example.org/doc/view', 'Document')])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                entries(html, PUBLIC)

    def fixture(self):
        text, map_url, folder = PLANNING + '/text/view', PLANNING + '/map/view', PUBLIC + '/aula'
        sources = {
            PLANNING: listing([('file', text, 'Text refós de caràcter informatiu que incorpora el Planejament vigent'),
                               ('file', map_url, 'Classificació del sòl')]),
            PUBLIC: listing([('folder', folder, 'Projecte d’actuació específica per a la implantació d’una aula rural al sòl no urbanitzable'),
                             ('folder', PUBLIC + '/bar', 'Informació pública llicència d’activitat Bar musical')]),
            folder: listing([('file', folder + '/anunci/view', 'Anunci Bop'),
                             ('file', folder + '/projecte/view', 'Projecte aula rural')]),
        }
        for url in (text, map_url, folder + '/anunci/view', folder + '/projecte/view'):
            sources[url] = f'<div id="content-core"><a href="{url[:-5]}/@@download/file">PDF</a></div>'
        return sources

    def test_groups_documents_and_leaves_unverified_semantics_null(self):
        adapter = TorrefarreraAyuntamientoAdapter('torrefarrera')
        sources = self.fixture()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            out = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            first = out.read_text()
            rows = [json.loads(line) for line in first.splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])
            for row in rows:
                for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                    self.assertIsNone(row[field])
                self.assertFalse(row['publication_ready'])
            adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(out.read_text(), first)

    def test_missing_attachment_fails_without_replacing_existing_output(self):
        adapter = TorrefarreraAyuntamientoAdapter('torrefarrera')
        sources = self.fixture()
        sources[PLANNING + '/text/view'] = '<div id="content-core">Unavailable</div>'
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous valid snapshot')
            with self.assertRaisesRegex(ValueError, 'unique download'):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous valid snapshot')

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(TorrefarreraAyuntamientoAdapter('torrefarrera').backfill_licencias(out)['status'], 'disabled')
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
