import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santanyi import (
    SOURCE, SantanyiAyuntamientoAdapter, group_instruments, parse_page,
)


def page(body):
    return '<main><div class="layout-content"><h1>Inventory</h1>' + body + '</div></main>'


def folder(path, title, count):
    return (f'<div class="taxonomy-term-files"><a href="{path}"><h3>{title}</h3>'
            f'<p>{count} documents</p></a></div>')


def document(title, filename):
    return (f'<article><div><h3>{title}</h3><span>15/03/2021</span>'
            f'<a download href="https://ajsantanyi.net/sites/cilma_santanyi/files/{filename}">'
            'Descarregar</a></div></article>')


class SantanyiTests(unittest.TestCase):
    def test_group_and_preserve_bilingual_documents(self):
        folders = {
            SOURCE + '/mod-93': {'url': SOURCE + '/mod-93', 'title': 'MOD 93 ESMENA DEFICIÈNCIES CIU', 'count': 1},
            SOURCE + '/boib': {'url': SOURCE + '/boib', 'title': 'BOIB MP 93', 'count': 2},
        }
        docs = {}
        for target, titles in [(SOURCE + '/mod-93', ['Memoria']),
                               (SOURCE + '/boib', ['BOIB MARÇ MP 93', 'BOIB MARZO MP 93'])]:
            html = page(''.join(document(t, str(i) + t + '.pdf') for i, t in enumerate(titles)))
            docs[target] = parse_page(html, target)[1]
        rows = group_instruments(folders, docs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['documentos'][0]['fecha_web_documento'], '2021-03-15')
        for field in ['fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'fase']:
            self.assertIsNone(rows[0][field])

    def test_navigation_and_form_are_not_projects(self):
        for html in ['<html>Login</html>', page('<a href="/form.pdf">Sol·licitud de llicència</a>')]:
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    def test_unassigned_notice_and_count_mismatch_fail(self):
        f = {'x': {'url': 'x', 'title': 'MOD 94', 'count': 2}}
        with self.assertRaisesRegex(ValueError, 'count'):
            group_instruments(f, {'x': [{'url': 'one', 'titulo': 'Memoria'}]})
        f['x']['count'] = 1
        f['b'] = {'url': 'b', 'title': 'BOIB', 'count': 1}
        with self.assertRaisesRegex(ValueError, 'associate'):
            group_instruments(f, {'x': [{'url': 'one', 'titulo': 'Memoria'}],
                                  'b': [{'url': 'two', 'titulo': 'MP 95'}]})

    def test_paginated_inventory_and_folder_full_snapshot(self):
        target = SOURCE + '/mod-94'
        pages = {
            SOURCE: page(folder(target, 'MOD 94', 2) + f'<a rel="next" href="{SOURCE}?page=1">Next</a>'),
            SOURCE + '?page=1': page(folder(target, 'MOD 94', 2)),
            target: page(document('Memoria', 'mem.pdf') + f'<nav class="pager"><a href="{target}?page=1">2</a></nav>'),
            target + '?page=1': page(document('Plano', 'plano.pdf')),
        }
        adapter = SantanyiAyuntamientoAdapter('santanyi')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            out = Path(tmp) / 'projects.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state')
            row = json.loads(out.read_text())
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(row['codigo_ine'], '07057')
            self.assertFalse(row['publication_ready'])

    def test_pagination_outside_inventory_fails(self):
        adapter = SantanyiAyuntamientoAdapter('santanyi')
        html = page(folder(SOURCE + '/mod-94', 'MOD 94', 1) + '<a rel="next" href="https://example.org">Next</a>')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=html):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                adapter.backfill_proyectos(Path(tmp) / 'out.jsonl')
            self.assertFalse((Path(tmp) / 'out.jsonl').exists())

    def test_identity_stable_and_licences_disabled(self):
        adapter = SantanyiAyuntamientoAdapter('santanyi')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
