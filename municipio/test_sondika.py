import json
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.sondika import (
    BASE, WEB, SOURCE, SondikaAyuntamientoAdapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


class SondikaTests(unittest.TestCase):
    def test_inventory_deduplicates_and_excludes_navigation(self):
        html = '''<a href="/licencia.aspx">Licencia</a><div class="main-content-right">
        <div class="link-item"><a href="proyecto.aspx">Proyecto técnico</a></div>
        <div class="link-item"><a href="proyecto.aspx">Proyecto técnico</a></div></div>'''
        rows = SondikaAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(rows, {WEB + '/Paginas/proyecto.aspx': 'Proyecto técnico'})
        for invalid in ['', '<div class="main-content-right"></div>',
                        '<div class="main-content-right"><a rel="next" href="?page=2">2</a></div>']:
            with self.assertRaises(ValueError):
                SondikaAyuntamientoAdapter.parse_inventory(invalid)

    def test_library_pagination_and_cycle(self):
        adapter = SondikaAyuntamientoAdapter('sondika')
        pages = {BASE + '/one': {'d': {'results': [1], '__next': '/two'}},
                 BASE + '/two': {'d': {'results': [2]}}}
        adapter._fetch = lambda url, as_json=False: pages[url]
        self.assertEqual(adapter._items(BASE + '/one'), [1, 2])
        pages[BASE + '/two']['d']['__next'] = '/one'
        with self.assertRaisesRegex(ValueError, 'cycle'):
            adapter._items(BASE + '/one')
        pages[BASE + '/one']['d']['__next'] = 'https://example.org/private'
        with self.assertRaisesRegex(ValueError, 'Unexpected source'):
            adapter._items(BASE + '/one')

    def test_document_grouping_and_complete_extraction(self):
        library_id = '1234'
        library = {'Id': library_id, 'RootFolder': {'ServerRelativeUrl':
                   '/es-ES/Ayuntamiento/Normas-Subsidiarias/obra'}}
        path = library['RootFolder']['ServerRelativeUrl'] + '/memoria.pdf'
        inventory = '<div class="main-content-right"><div class="link-item"><a href="obra.aspx">Proyecto de obra</a></div></div>'
        detail = '<div class="main-content-right"><td class="CSPFileName"><a href="' + path + '">Memoria</a></td></div>'
        items = [{'FSObjType': 0, 'FileRef': path, 'FileLeafRef': 'memoria.pdf'},
                 {'FSObjType': 0, 'FileRef': path.replace('memoria', 'planos'), 'FileLeafRef': 'planos.pdf'}]
        adapter = SondikaAyuntamientoAdapter('sondika')
        def fetch(url, as_json=False):
            if url == SOURCE:
                return inventory
            if not as_json:
                return detail
            return {'d': {'results': items if '/items?' in url else [library]}}
        adapter._fetch = fetch
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'projects.jsonl'
            adapter.backfill_proyectos(out)
            row = json.loads(out.read_text())
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(row['codigo_ine'], '48904')
            for key in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertIsNone(row[key])
            original_id = row['id']
            adapter.update_proyectos(out, Path(d) / 'state.json')
            self.assertEqual(json.loads(out.read_text())['id'], original_id)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        with self.assertRaises(ValueError):
            adapter.document_libraries(detail, SOURCE, [])
        with self.assertRaises(ValueError):
            adapter.parse_documents([], SOURCE)

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('sondika')
        self.assertIsInstance(load_portal_adapter(manifest), SondikaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Bizkaia')


if __name__ == '__main__':
    unittest.main()
