"""Offline parser/transport tests; no network, database or publication."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arrigorriaga import (
    BASE, PLANS, SOURCE, ArrigorriagaAyuntamientoAdapter,
    parse_file_page, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory():
    sections = []
    for index, title in enumerate(PLANS):
        if title == 'Plan de Acción del Paisaje de Arrigorriaga':
            body = '<a href="/media/paisaje.pdf">Diagnóstico</a>'
        else:
            body = '<script class="file-list-widget-config" type="application/json">' + json.dumps({
                'base_url': '/api/v1/', 'folder_id': index + 1,
                'category_id': None}) + '</script>'
        sections.append(f'<button aria-controls="p{index}">{title}</button>'
                        f'<div id="p{index}">{body}</div>')
    return ''.join(sections) + '<a href="/solicitud-licencia.pdf">Solicitud de licencia</a>'


def file_row(name):
    return {'url': '/media/' + name + '.pdf', 'name': name + '.pdf',
            'description': name, 'extension': 'pdf',
            'created_at': '2026-04-14T13:00:00+02:00'}


def page(rows, total=None):
    total = len(rows) if total is None else total
    return {'data': rows, 'recordsTotal': total, 'recordsFiltered': total}


class ArrigorriagaTests(unittest.TestCase):
    def test_inventory_groups_only_reviewed_plans(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]['documents'][0]['url'], BASE + '/media/paisaje.pdf')
        self.assertEqual([len(row['documents']) for row in rows], [0, 0, 0, 1])
        self.assertEqual(rows[1]['folders'], [(BASE + '/api/v1/', 2)])

    def test_changed_empty_or_paginated_inventory_fails(self):
        for html in ['', inventory().replace('Plan de Accesibilidad', 'Otro plan'),
                     inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory().replace('/api/v1/', 'https://other.example/api/v1/')]:
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_file_schema_and_filtering_fail_closed(self):
        for payload in [{}, page([file_row('a')], 0),
                        {'data': [], 'recordsTotal': 4, 'recordsFiltered': 2}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_file_page(payload)

    def test_pagination_continues_and_detects_ignored_offset(self):
        adapter = ArrigorriagaAyuntamientoAdapter('arrigorriaga')
        with patch.object(adapter, '_get', side_effect=[page([file_row('a')], 2),
                                                       page([file_row('b')], 2)]) as get:
            documents = adapter._files(BASE + '/api/v1/', 1, 2)
            self.assertEqual(len(documents), 2)
            self.assertIn('start=1', get.call_args_list[1].args[0])
        for responses in [[page([file_row('a')], 2), page([file_row('a')], 2)],
                          [page([file_row('a')], 2), page([], 2)],
                          [page([file_row('a')], 1)]]:
            with patch.object(adapter, '_get', side_effect=responses), self.assertRaises(ValueError):
                adapter._files(BASE + '/api/v1/', 1, 2)

    def test_recursive_folders_and_instrument_grouping(self):
        adapter = ArrigorriagaAyuntamientoAdapter('arrigorriaga')

        def get(url, as_json=False):
            if url == SOURCE:
                return inventory()
            if '/recursive/' in url:
                fid = int(url.split('/folder/')[1].split('/')[0])
                return {'id': fid, 'name': 'Root', 'files': 1,
                        'children': [{'id': 20, 'name': 'Propuestas', 'files': 1,
                                      'children': []}] if fid == 2 else []}
            from urllib.parse import parse_qs, urlparse
            fid = parse_qs(urlparse(url).query)['folder'][0]
            return page([file_row('doc-' + fid)])

        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=get):
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['count'], 4)
            self.assertEqual([len(row['documentos']) for row in rows], [1, 2, 1, 1])
            self.assertEqual(rows[1]['documentos'][1]['folder_name'], 'Propuestas')
            for row in rows:
                for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob',
                              'lat', 'lon', 'latitud', 'longitud', 'fase']:
                    self.assertNotIn(field, row)
                self.assertEqual(row['codigo_ine'], '48011')
                self.assertFalse(row['publication_ready'])
            previous = path.read_bytes()
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(previous, path.read_bytes())

    def test_failed_extraction_preserves_previous_output(self):
        adapter = ArrigorriagaAyuntamientoAdapter('arrigorriaga')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', return_value=''):
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous\n')

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('arrigorriaga')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('48011', 'Arrigorriaga', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ArrigorriagaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp, patch('requests.get', side_effect=AssertionError('network')):
            path = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
